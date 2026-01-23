#!/usr/bin/env python3
from __future__ import annotations

import os
import re
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    create_engine, MetaData, Table, Column,
    Integer, String, insert, update, select
)
from sqlalchemy.exc import IntegrityError


VOLUNTEERS_TEXT = r"""
PEDRO LUCAS - 85998193804
JUVENIR - +55 85 98541-9496
Berg - +55 85 99146-3735
Dan Costa - +55 85 98639-1469
Dudu - +55 85 98869-2058
José jr. - +55 85 98773-0227
Maicon - +55 85 98700-8599
Marcos - +55 85 98502-0180
Vinicius - +55 85 98173-1775
Alessandra - ‪+55 85 99685-1702‬
Anny - ‪+55 85 98186-2592‬
Ângelo - +55 85 98419-3810
Caio Filipe  - ‪+55 85 99146-1841‬
Carlos calacio - ‪+55 85 99791-3117‬
Carlos damasceno - ‪+55 85 99630-3823‬
Daniel andrews - ‪+55 85 99747-1066‬
Daniel Farias - ‪+55 85 99812-2758‬
Davison - ‪+55 85 99834-2995‬
Diego Peixoto - ‪+55 85 99961-4503‬
Felipe - ‪+55 85 99247-0008‬
Gabriel - ‪+55 85 98693-0299‬
Henrique - ‪+55 85 99235-1001‬
Mael - ‪+55 85 98631-9952‬
Nagila - ‪+55 85 99660-5707‬
Renan castro - ‪+55 85 99751-5457‬
Tiago Silveira - +55 85 99793-1305
Davi - +55 85 99418-5302
""".strip()

DEFAULTS = dict(
    active=1,
    thu_ok=1,
    sun_ok=1,
    can_obs=1,
    can_fixed=1,
    can_mobile=1,
)

def normalize_phone(raw: str) -> Optional[str]:
    if not raw:
        return None
    raw = raw.replace("\u202a", "").replace("\u202c", "").replace("\u200e", "").replace("\u200f", "")
    raw = raw.replace("‪", "").replace("‬", "")
    digits = re.sub(r"\D+", "", raw)
    if not digits:
        return None
    if digits.startswith("55") and len(digits) >= 12:
        return "+" + digits
    if len(digits) in (10, 11):
        return "+55" + digits
    return digits

def parse_lines(text: str):
    out = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        cleaned = line.replace("—", "-").replace("–", "-")
        if "-" in cleaned:
            name, phone = cleaned.split("-", 1)
            name = name.strip()
            phone = phone.strip()
        else:
            name, phone = cleaned.strip(), ""
        if name:
            out.append((name, normalize_phone(phone) if phone else None))
    return out

def main():
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        raise SystemExit("DATABASE_URL not set.")

    engine = create_engine(db_url, future=True)
    metadata = MetaData()

    # Define ONLY the volunteers table (minimal) and create if missing
    volunteers = Table(
        "volunteers", metadata,
        Column("id", Integer, primary_key=True),
        Column("name", String, nullable=False, unique=True),
        Column("phone", String, nullable=True),
        Column("active", Integer, nullable=False, default=1),
        Column("thu_ok", Integer, nullable=False, default=1),
        Column("sun_ok", Integer, nullable=False, default=1),
        Column("can_obs", Integer, nullable=False, default=1),
        Column("can_fixed", Integer, nullable=False, default=1),
        Column("can_mobile", Integer, nullable=False, default=1),
    )

    metadata.create_all(engine)

    items = parse_lines(VOLUNTEERS_TEXT)
    inserted, updated = 0, 0

    with engine.begin() as conn:
        for name, phone in items:
            data = {"name": name, "phone": phone, **DEFAULTS}
            try:
                conn.execute(insert(volunteers).values(**data))
                inserted += 1
            except IntegrityError:
                conn.execute(
                    update(volunteers)
                    .where(volunteers.c.name == name)
                    .values(phone=phone, **DEFAULTS)
                )
                updated += 1

    print(f"Done. Inserted: {inserted}, Updated: {updated}, Total: {len(items)}")

if __name__ == "__main__":
    main()