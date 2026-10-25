"""Read original ZIP bytes in place; never rewrite or bulk-extract them."""
from datetime import datetime, timezone
import hashlib
from pathlib import Path, PurePosixPath
import re
from zipfile import ZipFile

SOURCE = "https://data.mendeley.com/datasets/zh58byr53c/2"
DOI = "10.17632/zh58byr53c.2"
RUN = re.compile(r"^(M[12])_(NMC|NCA|Mixed)_(Aged|Unaged)_R([013])_T(10|25|40)$")


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def locate_archive(root):
    candidates = list(Path(root).glob("Full factorial*.zip")) + list(Path(root).glob("data/raw/*.zip"))
    if len(candidates) != 1:
        raise ValueError(f"Expected exactly one dataset ZIP; found {len(candidates)}. Use --archive.")
    return candidates[0]


def run_factors(stem):
    m = RUN.fullmatch(stem)
    if not m:
        raise ValueError(f"Unexpected experiment name: {stem}")
    module, chemistry, ageing, resistance, temperature = m.groups()
    return dict(run_id=stem, module=module, chemistry=chemistry, ageing_label=ageing,
                interconnect_mohm=int(resistance), interconnect_ohm=int(resistance) * 1e-3,
                ambient_setpoint_C=int(temperature))


class Archive:
    def __init__(self, path):
        self.path = Path(path)
        self.zip = ZipFile(path)
        self.names = [i.filename for i in self.zip.infolist() if not i.is_dir()]
        if len(set(self.names)) != len(self.names):
            raise ValueError("Duplicate ZIP member names")
        for name in self.names:
            p = PurePosixPath(name)
            if p.is_absolute() or ".." in p.parts:
                raise ValueError("Unsafe archive member path")

    def close(self):
        self.zip.close()

    def find(self, basename):
        found = [n for n in self.names if PurePosixPath(n).name == basename]
        if len(found) != 1:
            raise ValueError(f"Expected one {basename}; found {len(found)}")
        return found[0]

    def read(self, basename):
        return self.zip.read(self.find(basename))

    def inventory(self):
        records = []
        for name in self.names:
            info = self.zip.getinfo(name)
            h = hashlib.sha256()
            with self.zip.open(name) as f:
                for block in iter(lambda: f.read(1024 * 1024), b""):
                    h.update(block)
            # ZIP reads also check each member's stored CRC at end-of-file.
            records.append(dict(member=name, basename=PurePosixPath(name).name,
                bytes=info.file_size, sha256=h.hexdigest(), crc32=f"{info.CRC:08x}",
                data_origin="measured_raw_export" if name.endswith(".xlsx") else "author_processed_measurements",
                content_inspection="inventory_and_integrity_only"))
        return records

    def provenance(self):
        return dict(archive_name=self.path.name, bytes=self.path.stat().st_size,
                    sha256=sha256_file(self.path), source_url=SOURCE, doi=DOI, version=2,
                    access_date="2026-10-24", inspected_at_utc=datetime.now(timezone.utc).isoformat(),
                    retrieval="User downloaded the full official dataset ZIP and placed it in the workspace.",
                    version_assurance="User-supplied archive; matches documented v2 layout. No publisher checksum or embedded version manifest was available.",
                    licence="CC BY 4.0 (official dataset record, checked 2026-10-24)")
