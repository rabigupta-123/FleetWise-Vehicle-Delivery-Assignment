import pytest
from fastapi.testclient import TestClient


def test_phone_e164_normalization_and_metadata(client: TestClient, temp_db: str):
    # Create driver
    client.post("/drivers", json={"driver_id": "DR-PH-01", "name": "Phone Tester", "phone": "+91 98765 43210"})

    # Update with US number formatted loosely
    res_us = client.patch("/drivers/DR-PH-01/phone", json={"phone": "+1 (415) 555-2671"})
    assert res_us.status_code == 200
    data_us = res_us.json()
    assert data_us["phone"] == "+1 (415) 555-2671"
    assert data_us["phone_e164"] == "+14155552671"
    assert data_us["phone_country_code"] == "1"
    assert data_us["phone_verification_status"] == "unverified"

    # Update with Indian mobile number
    res_in = client.patch("/drivers/DR-PH-01/phone", json={"phone": "+91-9876543210"})
    assert res_in.status_code == 200
    data_in = res_in.json()
    assert data_in["phone_e164"] == "+919876543210"
    assert data_in["phone_country_code"] == "91"

    # Malformed phone number rejected with 400
    res_bad = client.patch("/drivers/DR-PH-01/phone", json={"phone": "123"})
    assert res_bad.status_code == 400
    assert res_bad.json()["error"] == "VALIDATION_ERROR"


def test_phone_verification_challenge_flow(client: TestClient, temp_db: str):
    # Setup driver with phone
    client.post("/drivers", json={"driver_id": "DR-PH-02", "name": "OTP Tester", "phone": "+1-415-555-2671"})
    client.patch("/drivers/DR-PH-02/phone", json={"phone": "+1-415-555-2671"})

    # 1. Request verification challenge
    res_req = client.post("/drivers/DR-PH-02/phone/request-verification")
    assert res_req.status_code == 200
    chal = res_req.json()
    assert chal["status"] == "pending"
    assert chal["verification_id"].startswith("VRF-")
    assert "dev_verification_code" in chal
    code = chal["dev_verification_code"]
    verification_id = chal["verification_id"]

    # Driver status should be 'pending'
    drv = client.get("/drivers").json()
    d_obj = [d for d in drv if d["driver_id"] == "DR-PH-02"][0]
    assert d_obj["phone_verification_status"] == "pending"

    # 2. Submit wrong code
    res_bad_code = client.post("/drivers/DR-PH-02/phone/verify", json={
        "verification_id": verification_id,
        "code": "000000",
    })
    assert res_bad_code.status_code == 400
    assert res_bad_code.json()["error"] == "INVALID_CODE"
    assert "attempts remaining" in res_bad_code.json()["message"]

    # 3. Submit correct code
    res_ok = client.post("/drivers/DR-PH-02/phone/verify", json={
        "verification_id": verification_id,
        "code": code,
    })
    assert res_ok.status_code == 200
    assert res_ok.json()["status"] == "verified"

    # Driver status should now be 'verified'
    drv_after = client.get("/drivers").json()
    d_verified = [d for d in drv_after if d["driver_id"] == "DR-PH-02"][0]
    assert d_verified["phone_verification_status"] == "verified"

    # Re-submitting on already verified challenge fails with 400
    res_re = client.post("/drivers/DR-PH-02/phone/verify", json={
        "verification_id": verification_id,
        "code": code,
    })
    assert res_re.status_code == 400
    assert res_re.json()["error"] == "CHALLENGE_INACTIVE"
