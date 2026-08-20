"""백업 암호화 — 되돌릴 수 있고, 변조를 잡는가.

백업 덤프에는 가계부 거래 전부와 계정 해시가 들어 있다. 파일 하나가 곧 전체
데이터베이스이고, 백업은 본체보다 관리가 허술한 곳으로 옮겨 다닌다.

여기서 고정하는 것은 셋이다.
  1. 암호화한 것을 **되돌릴 수 있는가** (복원 못 하는 백업은 백업이 아니다)
  2. **변조를 잡는가** (조용히 손상된 백업만큼 나쁜 것이 없다)
  3. 같은 내용을 두 번 암호화해도 **같은 바이트가 나오지 않는가**
     (GCM 은 논스를 재사용하면 암호가 통째로 깨진다)
"""
from __future__ import annotations

import secrets

import pytest

from scripts import backup_crypt as BC

KEY = secrets.token_hex(32)
PLAIN = b"PGDMP\x00" + b"\xde\xad\xbe\xef" * 500 + "가계부 거래".encode("utf-8")


@pytest.fixture
def dump(tmp_path, monkeypatch):
    monkeypatch.setenv(BC.KEY_ENV, KEY)
    p = tmp_path / "investment_20260820.dump"
    p.write_bytes(PLAIN)
    return p


def test_round_trip(dump) -> None:
    """복원 못 하는 백업은 백업이 아니다."""
    enc = BC.encrypt(dump, remove_source=False)
    assert enc.read_bytes()[:5] == BC.MAGIC
    dump.unlink()
    out = BC.decrypt(enc)
    assert out.read_bytes() == PLAIN


def test_library_call_does_not_delete_by_default(dump) -> None:
    """라이브러리 함수가 기본으로 파일을 지우면 위험하다 — 호출부가 원할 때만 지운다."""
    BC.encrypt(dump)
    assert dump.exists()


def test_plaintext_can_be_removed_explicitly(dump) -> None:
    """평문을 남기면 암호화한 의미가 없다. 백업 스크립트는 이 경로로 부른다."""
    BC.encrypt(dump, remove_source=True)
    assert not dump.exists()


def test_ciphertext_does_not_contain_the_plaintext(dump) -> None:
    enc = BC.encrypt(dump, remove_source=False)
    blob = enc.read_bytes()
    assert b"PGDMP" not in blob[5:]
    assert "가계부 거래".encode("utf-8") not in blob


def test_nonce_is_never_reused(dump, tmp_path) -> None:
    """GCM 에서 같은 키로 논스를 재사용하면 **암호가 통째로 깨진다** — 평문 복원까지
    가능해진다. 같은 내용을 두 번 암호화해도 결과가 달라야 한다."""
    a = BC.encrypt(dump, tmp_path / "a.enc", remove_source=False)
    b = BC.encrypt(dump, tmp_path / "b.enc", remove_source=False)
    assert a.read_bytes() != b.read_bytes()
    nonce_a = a.read_bytes()[5:5 + BC.NONCE_LEN]
    nonce_b = b.read_bytes()[5:5 + BC.NONCE_LEN]
    assert nonce_a != nonce_b


def test_tampering_is_detected(dump, tmp_path) -> None:
    """조용히 손상된 백업만큼 나쁜 것이 없다. 인증 암호라 복호화에서 걸려야 한다."""
    enc = BC.encrypt(dump, remove_source=False)
    blob = bytearray(enc.read_bytes())
    blob[-1] ^= 0x01                       # 한 비트만 뒤집는다
    bad = tmp_path / "tampered.enc"
    bad.write_bytes(bytes(blob))
    with pytest.raises(SystemExit):
        BC.decrypt(bad)


def test_wrong_key_is_rejected(dump, tmp_path, monkeypatch) -> None:
    enc = BC.encrypt(dump, remove_source=False)
    monkeypatch.setenv(BC.KEY_ENV, secrets.token_hex(32))
    with pytest.raises(SystemExit):
        BC.decrypt(enc)


def test_missing_key_fails_loudly(dump, monkeypatch) -> None:
    """키가 없는데 조용히 평문으로 두면 최악이다 — 시끄럽게 실패해야 한다.

    키는 두 곳에서 온다(환경변수 → .env). **둘 다** 비워야 '없음' 이다 — 한쪽만
    지우고 검증하면 폴백 때문에 통과해 버린다(실제로 그렇게 깨졌다).
    """
    from app.core.config import get_settings

    monkeypatch.delenv(BC.KEY_ENV, raising=False)
    monkeypatch.setattr(get_settings(), "backup_key", "", raising=False)
    with pytest.raises(SystemExit):
        BC.encrypt(dump)


def test_key_falls_back_to_settings(dump, monkeypatch) -> None:
    """스케줄러가 환경변수를 안 넘겨도 .env 의 키로 암호화된다 — 매번 셸에 넣다가
    빠뜨리면 그날 백업이 조용히 평문으로 남는다."""
    from app.core.config import get_settings

    monkeypatch.delenv(BC.KEY_ENV, raising=False)
    monkeypatch.setattr(get_settings(), "backup_key", KEY, raising=False)
    enc = BC.encrypt(dump, remove_source=False)
    assert enc.read_bytes()[:5] == BC.MAGIC


def test_short_key_is_rejected(dump, monkeypatch) -> None:
    """32바이트가 아닌 키를 조용히 늘리거나 자르면 안 된다."""
    monkeypatch.setenv(BC.KEY_ENV, secrets.token_hex(8))
    with pytest.raises(SystemExit):
        BC.encrypt(dump)


def test_foreign_file_is_rejected(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv(BC.KEY_ENV, KEY)
    p = tmp_path / "not-ours.enc"
    p.write_bytes(b"whatever")
    with pytest.raises(SystemExit):
        BC.decrypt(p)
