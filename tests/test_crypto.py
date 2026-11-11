import pytest
from dashboard.crypto import encrypt, decrypt

def test_round_trip():
    assert decrypt(encrypt({"a": "é"}, "pw"), "pw") == {"a": "é"}

def test_wrong_passphrase_raises():
    with pytest.raises(Exception):
        decrypt(encrypt({"a": 1}, "pw"), "nope")

def test_fresh_salt_and_iv_each_time():
    a, b = encrypt({}, "pw"), encrypt({}, "pw")
    assert a["salt"] != b["salt"] and a["iv"] != b["iv"]
