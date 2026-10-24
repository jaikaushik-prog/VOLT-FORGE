"""The inventory must not decode a single measurement row."""
import importlib.util
from pathlib import Path
import pytest

spec = importlib.util.spec_from_file_location('freetwinev_inventory',Path(__file__).parents[1]/'scripts/inventory_freetwinev.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_header_does_not_decode_measurement_bytes(tmp_path):
    path=tmp_path/'fixture.csv'
    # Deliberately invalid UTF-8 after the header: a full-file/text-buffer read fails.
    path.write_bytes(b'\xef\xbb\xbftimesamp,current,voltage\n\xff\xfeUNOPENED_OUTCOME')
    assert module.csv_header(path)==['timesamp','current','voltage']
    assert path.read_bytes().endswith(b'\xff\xfeUNOPENED_OUTCOME')


@pytest.mark.parametrize('content',[b'time,current,current\n',b'time,,voltage\n',b'time,current',b'a'*65537+b'\n'],ids=['duplicate','empty','unterminated','oversized'])
def test_ambiguous_or_invalid_headers_rejected(tmp_path,content):
    path=tmp_path/'fixture.csv'
    path.write_bytes(content)
    with pytest.raises(ValueError):module.csv_header(path)
