"""백업 덤프 암·복호화.

    python -m scripts.backup_crypt encrypt data/backups/x.dump
    python -m scripts.backup_crypt decrypt data/backups/x.dump.enc
    python -m scripts.backup_crypt keygen

왜 필요한가
-----------
덤프에는 **가계부 거래 전부와 계정 비밀번호 해시**가 들어 있다. 파일 하나가 곧 전체
데이터베이스이고, 백업은 원래 본체보다 관리가 허술한 곳(외장 디스크·클라우드 드라이브)
으로 옮겨 다닌다. 옮기는 순간 접근통제도 RLS 도 따라가지 않는다 — 파일이니까.

설계
----
**AES-256-GCM.** 인증 암호라 복호화할 때 변조를 함께 잡는다. CBC 같은 것을 쓰면
암호문을 조작해도 복호화가 조용히 성공해서, 백업이 손상됐는지 알 수가 없다.

**키는 파일에 두지 않는다.** ``BACKUP_KEY`` 환경변수(hex 64자)에서 읽는다. 키를 덤프
옆에 두면 암호화한 의미가 없다.

**논스는 매번 새로 만든다.** GCM 에서 같은 키로 논스를 재사용하면 **암호가 통째로
깨진다** — 평문 복원까지 가능해진다. 파일 앞에 논스를 붙여 저장하고, 매 호출 새로 뽑는다.

파일 형식(단순하게 둔다 — 복구할 때 도구 없이도 읽을 수 있어야 한다)::

    "IVBK1"(5B) | nonce(12B) | ciphertext+tag
"""
from __future__ import annotations

import argparse
import os
import secrets
import sys
from pathlib import Path

MAGIC = b"IVBK1"
NONCE_LEN = 12
KEY_ENV = "BACKUP_KEY"


def _key() -> bytes:
    """환경변수를 먼저 보고, 없으면 앱 설정(.env)을 본다.

    환경변수를 우선하는 이유: 스케줄러나 CI 에서 키를 주입할 때 파일을 고치지 않아도
    되게 하려는 것이다. 로컬은 .env 한 곳에 두는 편이 실수가 적다 —— 매번 셸에
    넣다가 빠뜨리면 그날 백업이 조용히 평문으로 저장된다.
    """
    raw = os.environ.get(KEY_ENV, "").strip()
    if not raw:
        try:
            from app.core.config import get_settings
            raw = (get_settings().backup_key or "").strip()
        except Exception:  # noqa: BLE001
            raw = ""
    if not raw:
        raise SystemExit(
            f"{KEY_ENV} 가 없습니다. 키를 만들고 환경변수에 넣으세요:\n"
            f"  python -m scripts.backup_crypt keygen")
    try:
        key = bytes.fromhex(raw)
    except ValueError as e:
        raise SystemExit(f"{KEY_ENV} 는 hex 문자열이어야 합니다") from e
    if len(key) != 32:
        raise SystemExit(f"{KEY_ENV} 는 32바이트(hex 64자)여야 합니다 — 지금 {len(key)}바이트")
    return key


def encrypt(src: Path, dst: Path | None = None, *, remove_source: bool = False) -> Path:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    dst = dst or src.with_suffix(src.suffix + ".enc")
    # 논스는 **매번** 새로 뽑는다. 재사용하면 GCM 의 보안이 통째로 무너진다.
    nonce = secrets.token_bytes(NONCE_LEN)
    data = src.read_bytes()
    blob = AESGCM(_key()).encrypt(nonce, data, MAGIC)
    dst.write_bytes(MAGIC + nonce + blob)
    if remove_source:
        # 평문을 남기면 암호화한 의미가 없다.
        src.unlink()
    return dst


def decrypt(src: Path, dst: Path | None = None) -> Path:
    from cryptography.exceptions import InvalidTag
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    raw = src.read_bytes()
    if not raw.startswith(MAGIC):
        raise SystemExit(f"{src.name} 은 이 도구로 만든 파일이 아닙니다")
    nonce = raw[len(MAGIC):len(MAGIC) + NONCE_LEN]
    body = raw[len(MAGIC) + NONCE_LEN:]
    try:
        data = AESGCM(_key()).decrypt(nonce, body, MAGIC)
    except InvalidTag as e:
        # 키가 틀렸거나 파일이 변조·손상됐다. 둘을 구분해 주지 않는 것이 맞다 —
        # 구분해 주면 키를 맞춰 보는 공격에 힌트가 된다.
        raise SystemExit(f"{src.name} 복호화 실패 — 키가 다르거나 파일이 손상됐습니다") from e
    dst = dst or src.with_suffix("")
    dst.write_bytes(data)
    return dst


def main() -> None:
    ap = argparse.ArgumentParser(description="백업 덤프 암·복호화 (AES-256-GCM)")
    ap.add_argument("action", choices=["encrypt", "decrypt", "keygen"])
    ap.add_argument("path", nargs="?", type=Path)
    ap.add_argument("--keep", action="store_true",
                    help="암호화 후에도 평문 원본을 남긴다(기본은 지운다)")
    args = ap.parse_args()

    if args.action == "keygen":
        print(secrets.token_hex(32))
        print(f"\n이 값을 {KEY_ENV} 환경변수에 넣으세요. **덤프와 같은 곳에 두지 마세요** —",
              file=sys.stderr)
        print("키를 백업 옆에 두면 암호화한 의미가 없습니다.", file=sys.stderr)
        return

    if not args.path or not args.path.exists():
        raise SystemExit("대상 파일을 찾을 수 없습니다")

    if args.action == "encrypt":
        out = encrypt(args.path, remove_source=not args.keep)
        print(f"암호화: {out.name}  ({out.stat().st_size:,}B)")
    else:
        out = decrypt(args.path)
        print(f"복호화: {out.name}  ({out.stat().st_size:,}B)")


if __name__ == "__main__":
    main()
