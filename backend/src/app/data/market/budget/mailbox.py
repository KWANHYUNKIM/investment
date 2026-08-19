"""카드사 이용대금명세서를 **받은편지함에서 직접 걷어 오는** 수집기.

왜 메일인가
-----------
카드 이용내역을 자동으로 받아 올 길을 다 따져 봤는데 개인에게 열려 있는 게 없다.
마이데이터·오픈뱅킹 API 는 허가받은 사업자만 부를 수 있고, 카드사 개발자 포털은
제휴사용이며, 승인문자는 실시간이지만 **할부 회차·부분취소·청구월을 못 잡는다**
— 이 가계부는 청구월이 뼈대라 문자로는 애초에 채울 수가 없다.

남는 게 카드사가 매달 보내 주는 e-메일 이용대금명세서다. 월 1회지만 청구월과
할부가 확정된 원본이고, 필요한 자격증명이 **메일 계정 하나뿐**이라 카드사 로그인
정보를 어디에도 맡기지 않아도 된다.

무엇을 하는가
-------------
1. IMAP 으로 받은편지함을 읽는다(``readonly`` — 읽음 표시를 건드리지 않는다).
2. 보낸사람·제목으로 카드사 명세서를 골라낸다.
3. 첨부를 꺼낸다. zip 은 풀고, 암호가 걸린 엑셀/PDF 는 후보 비밀번호로 연다.
   첨부가 없으면 **본문 HTML 표**를 대신 읽는다(본문에 표를 넣는 카드사가 있다).
4. 기존 ``cards`` 파서에 그대로 태운다 — 파일 업로드와 같은 경로다.
5. 확신할 때만 자동 등록하고, 나머지는 **대기함**에 둔다.

자동 등록의 기준을 좁게 잡은 이유
---------------------------------
카드사마다 '금액' 이 뜻하는 게 다르다(할부 원금이냐 총액이냐, 수수료 포함이냐).
잘못 들어간 값은 몇 달 뒤 합계가 안 맞을 때야 드러나고, 그때는 어느 명세서가
범인인지 찾기 어렵다. 그래서 **전용 파서로 읽혔고 + 청구월이 확정됐고 +
카드 설정과 충돌이 없을 때만** 바로 넣고, 하나라도 어긋나면 대기함으로 보낸다.
추정으로 읽은 것(``generic``/``loose``)은 사람이 눈으로 보고 넣는 게 맞다.

원본 첨부는 ``data/budget_mail/`` 에 그대로 남긴다. 파싱이 틀렸을 때 원본이
없으면 무엇이 틀렸는지 확인할 방법이 없기 때문이다.
"""
from __future__ import annotations

import email
import hashlib
import imaplib
import io
import os
import re
import threading
import time
import zipfile
from email.header import decode_header, make_header
from email.utils import parsedate_to_datetime

from app.core.config import get_settings
from app.core.jsonstore import read_json, user_path, write_json

_lock = threading.Lock()

_DEFAULT: dict = {
    "seen": [],         # 이미 살펴본 메일 키 (최근 1000)
    "pending": [],      # 사람 확인 대기 중인 파싱 결과
    "history": [],      # 처리 이력 (최근 60)
    "last_scan": None,
}

_MAX_SEEN = 1000
_MAX_HISTORY = 60

# 전용 파서로 읽혔을 때만 자동 등록한다. generic·loose 는 추정이라 제외.
_TRUSTED_PARSERS = {"shinhan", "lotte", "hana", "samsung"}


# --- 어떤 메일이 명세서인가 -------------------------------------------------
# 보낸사람 도메인이 가장 확실하지만, 카드사가 발송 대행을 쓰면 도메인이 달라진다.
# 그래서 도메인 **또는** 제목의 카드사 이름 중 하나만 맞아도 후보로 본다.
_ISSUER_HINTS: dict[str, tuple[str, ...]] = {
    "신한카드": ("shinhancard.com", "shinhan.com", "신한카드"),
    "롯데카드": ("lottecard.co.kr", "롯데카드"),
    "하나카드": ("hanacard.co.kr", "hanabank.com", "하나카드"),
    "삼성카드": ("samsungcard.com", "삼성카드"),
    "현대카드": ("hyundaicard.com", "현대카드"),
    "KB국민카드": ("kbcard.com", "kbfg.com", "국민카드"),
    "우리카드": ("wooricard.com", "우리카드"),
    "NH농협카드": ("nonghyup.com", "nhcard.com", "농협카드"),
    "BC카드": ("bccard.com", "비씨카드"),
    "씨티카드": ("citi.com", "씨티카드"),
}

# 카드사 이름이 안 잡혀도 제목이 명세서면 후보로 올린다(발송 대행 도메인 대비).
_SUBJECT_HINTS = ("이용대금", "명세서", "청구금액", "결제예정", "이용내역", "카드대금")

# 명세서가 아닌데 위 키워드를 달고 오는 것들 — 광고·안내는 첨부가 없거나 쓸모없다.
_SUBJECT_BLOCK = ("이벤트", "광고", "혜택 안내", "회원님께 드리는", "설문")

_ATTACH_EXT = (".xls", ".xlsx", ".csv", ".txt", ".pdf", ".zip")
_INNER_EXT = tuple(e for e in _ATTACH_EXT if e != ".zip")   # zip 안의 zip 은 안 판다


def _path(user: str) -> str:
    return user_path("budget_mail", user)


def load(user: str) -> dict:
    return read_json(_path(user), _DEFAULT)


def save(user: str, d: dict) -> None:
    write_json(_path(user), d)


# --- 메일 헤더 -------------------------------------------------------------
def _decode(raw: str | None) -> str:
    """RFC2047 인코딩 헤더(``=?utf-8?B?...?=``)를 사람이 읽는 문자열로."""
    if not raw:
        return ""
    try:
        return str(make_header(decode_header(raw))).strip()
    except Exception:
        return str(raw).strip()


def _issuer_of(sender: str, subject: str) -> str:
    blob = f"{sender} {subject}".lower()
    for issuer, hints in _ISSUER_HINTS.items():
        if any(h.lower() in blob for h in hints):
            return issuer
    return ""


def _is_statement(sender: str, subject: str) -> bool:
    if any(b in subject for b in _SUBJECT_BLOCK):
        return False
    if _issuer_of(sender, subject):
        return True
    return any(k in subject for k in _SUBJECT_HINTS)


def _msg_key(msg, uid: bytes) -> str:
    mid = (msg.get("Message-ID") or "").strip()
    if mid:
        return mid[:200]
    blob = f'{uid!r}|{msg.get("Subject", "")}|{msg.get("Date", "")}'
    return "h:" + hashlib.sha1(blob.encode("utf-8", "replace")).hexdigest()


def _sent_at(msg) -> str:
    try:
        return parsedate_to_datetime(msg.get("Date")).strftime("%Y-%m-%d %H:%M")
    except Exception:
        return ""


# --- 잠긴 첨부 열기 ---------------------------------------------------------
class Locked(Exception):
    """비밀번호 후보로 열지 못했다."""


def _passwords() -> list[str]:
    raw = get_settings().budget_mail_passwords or ""
    return [p.strip() for p in raw.split(",") if p.strip()]


def _unlock_office(data: bytes, passwords: list[str]) -> bytes | None:
    """암호가 걸린 엑셀이면 풀어서 돌려준다. 안 걸려 있으면 ``None``."""
    try:
        import msoffcrypto
    except ImportError:
        return None
    try:
        if not msoffcrypto.OfficeFile(io.BytesIO(data)).is_encrypted():
            return None
    except Exception:
        return None                     # 엑셀이 아니거나 판별 불가 — 원본 그대로 간다
    for pw in passwords:
        try:
            # OfficeFile 은 실패한 키를 물고 있어 후보마다 새로 만든다.
            f = msoffcrypto.OfficeFile(io.BytesIO(data))
            f.load_key(password=pw)
            out = io.BytesIO()
            f.decrypt(out)
            return out.getvalue()
        except Exception:
            continue
    raise Locked("엑셀 첨부에 비밀번호가 걸려 있습니다")


def _unlock_pdf(data: bytes, passwords: list[str]) -> bytes | None:
    """암호가 걸린 PDF 면 풀어서 돌려준다. 안 걸려 있으면 ``None``."""
    try:
        from pypdf import PdfReader, PdfWriter
    except ImportError:
        return None
    try:
        if not PdfReader(io.BytesIO(data)).is_encrypted:
            return None
    except Exception:
        return None
    for pw in passwords:
        try:
            reader = PdfReader(io.BytesIO(data))
            if not reader.decrypt(pw):
                continue
            writer = PdfWriter()
            for page in reader.pages:
                writer.add_page(page)
            out = io.BytesIO()
            writer.write(out)
            return out.getvalue()
        except Exception:
            continue
    raise Locked("PDF 첨부에 비밀번호가 걸려 있습니다")


def _unlock(filename: str, data: bytes, passwords: list[str]) -> bytes:
    low = filename.lower()
    if low.endswith(".pdf") or data[:5].lstrip().startswith(b"%PDF"):
        return _unlock_pdf(data, passwords) or data
    return _unlock_office(data, passwords) or data


def _expand_zip(name: str, data: bytes, passwords: list[str]) -> list[tuple[str, bytes]]:
    """zip 첨부를 풀어 안의 파일들을 돌려준다(암호 zip 은 후보로 시도)."""
    out: list[tuple[str, bytes]] = []
    try:
        zf = zipfile.ZipFile(io.BytesIO(data))
    except Exception:
        return [(name, data)]
    for info in zf.infolist():
        if info.is_dir() or not info.filename.lower().endswith(_INNER_EXT):
            continue
        blob = None
        for pw in [None, *passwords]:
            try:
                blob = zf.read(info, pwd=pw.encode() if pw else None)
                break
            except Exception:
                continue
        if blob is None:
            raise Locked(f"압축 파일({name})에 비밀번호가 걸려 있습니다")
        out.append((os.path.basename(info.filename), blob))
    return out


# --- 첨부/본문 꺼내기 -------------------------------------------------------
def _attachments(msg) -> list[tuple[str, bytes]]:
    found: list[tuple[str, bytes]] = []
    for part in msg.walk():
        if part.get_content_maintype() == "multipart":
            continue
        name = _decode(part.get_filename())
        if not name or not name.lower().endswith(_ATTACH_EXT):
            continue
        try:
            payload = part.get_payload(decode=True)
        except Exception:
            payload = None
        if payload:
            found.append((name, payload))
    return found


def _html_body(msg) -> bytes:
    """본문 HTML — 첨부 없이 본문 표로 명세서를 보내는 카드사가 있다."""
    for part in msg.walk():
        if part.get_content_type() != "text/html":
            continue
        try:
            payload = part.get_payload(decode=True)
        except Exception:
            continue
        if payload:
            return payload
    return b""


_UNSAFE = re.compile(r"[^\w.\-가-힣]")


def _archive(user: str, sent_at: str, filename: str, data: bytes) -> str:
    """원본 첨부를 남긴다 — 파싱이 틀렸을 때 대조할 게 있어야 한다."""
    d = get_settings().data_dir / "budget_mail"
    try:
        d.mkdir(parents=True, exist_ok=True)
        stamp = (sent_at or time.strftime("%Y-%m-%d")).replace(":", "").replace(" ", "_")
        safe = _UNSAFE.sub("_", f"{user}_{stamp}_{filename}")[:120]
        p = d / safe
        with open(p, "wb") as fh:
            fh.write(data)
        return str(p)
    except Exception:
        return ""


# --- 파싱 결과를 어떻게 처리할지 --------------------------------------------
def _auto_ok(rep: dict) -> tuple[bool, str]:
    """자동 등록해도 되는가. 아니면 왜 안 되는가."""
    if not rep.get("transactions"):
        return False, "거래를 찾지 못함"
    if rep.get("parsed_by") not in _TRUSTED_PARSERS:
        return False, "전용 파서가 아닌 추정 파싱"
    if not rep.get("billing_month_known"):
        return False, "청구월 미확정"
    if rep.get("cycle_conflict"):
        return False, "카드 설정과 청구월 불일치"
    return True, ""


def _slim(rep: dict) -> dict:
    """대기함/이력에 남길 요약 — 거래 원본은 pending 에만 따로 담는다."""
    stats = rep.get("stats") or {}
    return {
        "issuer": rep.get("issuer", ""),
        "billing_month": rep.get("billing_month", ""),
        "billing_month_known": rep.get("billing_month_known", False),
        "parsed_by": rep.get("parsed_by", ""),
        "file_kind": rep.get("file_kind", ""),
        "count": len(rep.get("transactions") or []),
        "spend": stats.get("spend", 0),
        "date_range": stats.get("date_range", ["", ""]),
        "note": rep.get("note", ""),
        "cycle_conflict": rep.get("cycle_conflict"),
    }


# --- 수집 ------------------------------------------------------------------
def _connect(s):
    cls = imaplib.IMAP4_SSL if s.imap_ssl else imaplib.IMAP4
    conn = cls(s.imap_host, s.imap_port)
    conn.login(s.imap_user, s.imap_password)
    return conn


def configured() -> bool:
    s = get_settings()
    return bool(s.imap_host and s.imap_user and s.imap_password)


def scan(user: str | None = None, *, days: int | None = None,
         limit: int | None = None, rescan: bool = False) -> dict:
    """받은편지함을 훑어 명세서를 걷는다.

    ``rescan`` 이면 이미 살펴본 메일도 다시 본다(판별 규칙을 고쳤을 때 쓴다).
    """
    s = get_settings()
    user = user or s.budget_mail_user or "default"
    if not configured():
        return {"ok": False, "reason": "IMAP 미설정",
                "note": "IMAP_HOST/IMAP_USER/IMAP_PASSWORD 를 backend/.env 에 넣어 주세요.",
                "examined": 0, "imported": 0, "pending": 0}

    days = int(days or s.budget_mail_days)
    limit = int(limit or s.budget_mail_max)
    passwords = _passwords()
    since = time.strftime("%d-%b-%Y", time.localtime(time.time() - days * 86400))

    conn = _connect(s)
    try:
        conn.select(s.imap_folder, readonly=True)   # 읽음 표시를 바꾸지 않는다
        typ, data = conn.search(None, "SINCE", since)
        uids = data[0].split() if (typ == "OK" and data and data[0]) else []
        uids = uids[::-1][:limit]                   # 최신 메일부터
        seen = set(load(user)["seen"])
        results = [_handle_uid(conn, user, uid, passwords, seen, rescan) for uid in uids]
    finally:
        try:
            conn.close()
        except Exception:
            pass
        conn.logout()

    return _commit(user, [r for r in results if r], len(uids), days)


def _handle_uid(conn, user: str, uid: bytes, passwords: list[str],
                seen: set[str], rescan: bool) -> dict | None:
    """메일 한 통 → 처리 결과(또는 볼 것 없으면 ``None``). 저장은 하지 않는다."""
    typ, data = conn.fetch(uid, "(BODY.PEEK[])")
    if typ != "OK" or not data or not isinstance(data[0], tuple):
        return None
    msg = email.message_from_bytes(data[0][1])

    key = _msg_key(msg, uid)
    if key in seen and not rescan:
        return None

    sender = _decode(msg.get("From"))
    subject = _decode(msg.get("Subject"))
    if not _is_statement(sender, subject):
        return {"key": key, "skip": True}           # 살펴봤다는 표시만 남긴다

    sent_at = _sent_at(msg)
    parts = _collect_parts(msg, passwords)
    if isinstance(parts, str):                      # 잠겨서 못 연 경우 — 사유 문자열
        return {"key": key, "subject": subject, "sender": sender, "sent_at": sent_at,
                "locked": parts}
    if not parts:
        return {"key": key, "skip": True}

    from app.data.market import budget as budget_data   # 지연 import — 순환 참조 회피
    out = []
    for filename, blob in parts:
        rep = budget_data.preview_file(user, filename, blob)
        out.append({
            "filename": filename,
            "saved_path": _archive(user, sent_at, filename, blob),
            "rep": rep,
        })
    return {"key": key, "subject": subject, "sender": sender, "sent_at": sent_at,
            "issuer_hint": _issuer_of(sender, subject), "files": out}


def _collect_parts(msg, passwords: list[str]) -> list[tuple[str, bytes]] | str:
    """첨부(또는 본문 표) 를 파싱 가능한 바이트로. 못 열면 사유 문자열."""
    parts: list[tuple[str, bytes]] = []
    try:
        for name, blob in _attachments(msg):
            if name.lower().endswith(".zip"):
                parts.extend((n, _unlock(n, b, passwords))
                             for n, b in _expand_zip(name, blob, passwords))
            else:
                parts.append((name, _unlock(name, blob, passwords)))
    except Locked as e:
        return str(e)
    if parts:
        return parts
    body = _html_body(msg)
    # 본문은 안내문만 있는 경우가 대부분이라, 표가 실제로 있을 때만 후보로 본다.
    if body and b"<table" in body.lower():
        return [("메일본문.html", body)]
    return []


def _commit(user: str, results: list[dict], examined: int, days: int) -> dict:
    """스캔 결과를 한 번에 저장한다 — 중간에 죽어도 절반만 반영되지 않게."""
    from app.data.market import budget as budget_data

    imported = pending = locked = 0
    added_total = 0
    lines: list[str] = []

    with _lock:
        d = load(user)
        seen: list[str] = d["seen"]
        seen_set = set(seen)
        now = time.strftime("%Y-%m-%d %H:%M:%S")

        for r in results:
            if r["key"] not in seen_set:
                seen.append(r["key"])
                seen_set.add(r["key"])
            if r.get("skip"):
                continue
            if r.get("locked"):
                locked += 1
                d["history"].insert(0, {"at": now, "subject": r.get("subject", ""),
                                        "action": "locked", "reason": r["locked"]})
                lines.append(f'{r.get("subject", "")}: {r["locked"]}')
                continue

            for f in r["files"]:
                rep, summary = f["rep"], _slim(f["rep"])
                ok, why = _auto_ok(rep)
                base = {"at": now, "subject": r.get("subject", ""), "sender": r.get("sender", ""),
                        "sent_at": r.get("sent_at", ""), "filename": f["filename"],
                        "saved_path": f["saved_path"], **summary}
                if ok and get_settings().budget_mail_autoimport:
                    res = budget_data.add_transactions(user, rep["transactions"], source={
                        "filename": f'메일:{f["filename"]}', "issuer": rep["issuer"],
                        "billing_month": rep["billing_month"], "parsed_by": rep["parsed_by"],
                    })
                    imported += 1
                    added_total += res.get("added", 0)
                    d["history"].insert(0, {**base, "action": "imported", **res})
                    lines.append(f'{summary["issuer"] or "카드"} {summary["billing_month"]} '
                                 f'{res.get("added", 0)}건 등록')
                else:
                    pending += 1
                    d["pending"].insert(0, {
                        **base, "id": hashlib.sha1(
                            f'{r["key"]}|{f["filename"]}'.encode()).hexdigest()[:12],
                        "reason": why or "자동 등록 꺼짐",
                        "transactions": rep["transactions"],
                        "sample": rep["transactions"][:8],
                    })
                    lines.append(f'{summary["issuer"] or "카드"} {summary["billing_month"]} '
                                 f'{summary["count"]}건 — 확인 대기({why})')

        # 같은 명세서를 두 번 담지 않는다(재스캔·중복 발송).
        d["pending"] = _dedupe(d["pending"])
        d["seen"] = seen[-_MAX_SEEN:]
        d["history"] = d["history"][:_MAX_HISTORY]
        d["last_scan"] = {"at": now, "examined": examined, "days": days,
                          "imported": imported, "pending": pending, "locked": locked}
        save(user, d)

    return {"ok": True, "examined": examined, "imported": imported, "added": added_total,
            "pending": pending, "locked": locked, "days": days,
            "note": " · ".join(lines) if lines else "새 명세서가 없습니다."}


def _dedupe(pending: list[dict]) -> list[dict]:
    seen: set[str] = set()
    out: list[dict] = []
    for p in pending:
        if p["id"] in seen:
            continue
        seen.add(p["id"])
        out.append(p)
    return out


# --- 대기함 ----------------------------------------------------------------
def state(user: str) -> dict:
    """설정 상태 + 대기함 + 최근 이력. 비밀번호는 내보내지 않는다."""
    s = get_settings()
    d = load(user)
    return {
        "configured": configured(),
        "enabled": s.budget_mail,
        "autoimport": s.budget_mail_autoimport,
        "host": s.imap_host,
        "account": s.imap_user,
        "folder": s.imap_folder,
        "days": s.budget_mail_days,
        "interval_min": round(s.budget_mail_check_interval / 60),
        "has_passwords": bool(_passwords()),
        "last_scan": d.get("last_scan"),
        # 거래 원본은 무거워서 목록에서 뺀다 — 확인용 sample 만 남긴다.
        "pending": [{k: v for k, v in p.items() if k != "transactions"} for p in d["pending"]],
        "history": d["history"][:20],
        "issuers": sorted(_ISSUER_HINTS),
    }


def approve(user: str, item_id: str) -> dict:
    """대기함 항목을 실제 가계부에 등록한다."""
    from app.data.market import budget as budget_data
    with _lock:
        d = load(user)
        item = next((p for p in d["pending"] if p["id"] == item_id), None)
        if not item:
            return {"ok": False, "reason": "대기함에 없는 항목입니다"}
        res = budget_data.add_transactions(user, item["transactions"], source={
            "filename": f'메일:{item.get("filename", "")}', "issuer": item.get("issuer", ""),
            "billing_month": item.get("billing_month", ""),
            "parsed_by": item.get("parsed_by", ""),
        })
        d["pending"] = [p for p in d["pending"] if p["id"] != item_id]
        d["history"].insert(0, {**{k: v for k, v in item.items()
                                   if k not in ("transactions", "sample")},
                                "at": time.strftime("%Y-%m-%d %H:%M:%S"),
                                "action": "approved", **res})
        d["history"] = d["history"][:_MAX_HISTORY]
        save(user, d)
    return {"ok": True, **res, "issuer": item.get("issuer", ""),
            "billing_month": item.get("billing_month", "")}


def discard(user: str, item_id: str) -> dict:
    with _lock:
        d = load(user)
        before = len(d["pending"])
        d["pending"] = [p for p in d["pending"] if p["id"] != item_id]
        save(user, d)
    return {"ok": before != len(d["pending"])}


def detail(user: str, item_id: str) -> dict:
    """대기함 항목의 거래 전체 — 등록 전에 화면에서 훑어보기 위한 것."""
    item = next((p for p in load(user)["pending"] if p["id"] == item_id), None)
    if not item:
        return {"ok": False, "reason": "대기함에 없는 항목입니다"}
    return {"ok": True, **item}


__all__ = ["approve", "configured", "detail", "discard", "load", "scan", "state"]
