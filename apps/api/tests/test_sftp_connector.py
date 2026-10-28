from io import BytesIO
from types import SimpleNamespace

from app.integrations.connectors.sftp import SFTPConnector

CSV_PAYLOAD = b"""claim_number,patient_first_name,patient_last_name,medical_record_number,payer_code,billed_amount,paid_amount,service_date,status,denial_code,denial_reason,diagnosis_codes,procedure_codes
CLM-SFTP-001,Amina,Wanjiku,MRN-SFTP-001,AETNA,125000.00,0.00,2026-07-15,denied,CO-16,Missing information,I10,99213
"""


def test_parse_csv_returns_full_canonical_claim():
    connector = SFTPConnector(organization_id=1)

    claims = connector._parse_csv(CSV_PAYLOAD.decode(), "/claims/a.csv:100:1", "/claims/a.csv")

    assert len(claims) == 1
    claim = claims[0]
    assert claim.claim_number == "CLM-SFTP-001"
    assert claim.patient_first_name == "Amina"
    assert claim.patient_mrn == "MRN-SFTP-001"
    assert claim.diagnosis_codes == ["I10"]
    assert claim.procedure_codes == ["99213"]
    assert claim.external_id == "/claims/a.csv:100:1"


def test_fetch_claims_skips_processed_remote_file(monkeypatch):
    file_id = f"/claims/a.csv:{len(CSV_PAYLOAD)}:100"

    class FakeSFTP:
        def listdir_attr(self, path):
            assert path == "/claims"
            return [SimpleNamespace(filename="a.csv", st_size=len(CSV_PAYLOAD), st_mtime=100)]

        def open(self, path, mode):
            raise AssertionError("Processed file should not be opened")

        def close(self):
            pass

    class FakeClient:
        def open_sftp(self):
            return FakeSFTP()

        def close(self):
            pass

    connector = SFTPConnector(organization_id=1, processed_files=[file_id])
    monkeypatch.setattr(connector, "_client", lambda: FakeClient())

    assert connector._fetch_claims() == []


def test_fetch_claims_downloads_matching_csv(monkeypatch):
    class FakeSFTP:
        def listdir_attr(self, path):
            return [
                SimpleNamespace(filename="ignore.txt", st_size=1, st_mtime=100),
                SimpleNamespace(filename="claims.csv", st_size=len(CSV_PAYLOAD), st_mtime=101),
            ]

        def open(self, path, mode):
            assert path == "/claims/claims.csv"
            return BytesIO(CSV_PAYLOAD)

        def close(self):
            pass

    class FakeClient:
        def open_sftp(self):
            return FakeSFTP()

        def close(self):
            pass

    connector = SFTPConnector(organization_id=1)
    monkeypatch.setattr(connector, "_client", lambda: FakeClient())

    claims = connector._fetch_claims()

    assert [claim.claim_number for claim in claims] == ["CLM-SFTP-001"]
    assert claims[0].source_system == "sftp:/claims/claims.csv"
