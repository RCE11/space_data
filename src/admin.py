"""Admin CLI for managing the Space Data platform.

Usage:
    python -m src.admin stats
    python -m src.admin keys list
    python -m src.admin keys create <owner> [--tier free|individual|team]
    python -m src.admin keys deactivate <key_prefix>
    python -m src.admin search <query>
    python -m src.admin operator reassign <norad_id> <operator_name>
    python -m src.admin operator list [--country-only]
    python -m src.admin constellation set <norad_id> <constellation>
    python -m src.admin constellation clear <norad_id>
    python -m src.admin flag <norad_id> <note>
    python -m src.admin flags list
    python -m src.admin flags resolve <norad_id>
    python -m src.admin usage [--days 7] [--user <owner>]
"""

import hashlib
import secrets
import sys
from datetime import datetime

from dotenv import load_dotenv
from sqlalchemy import func, select, update

load_dotenv()

from src.db.connection import SessionLocal
from src.db.models import ApiKey, Launch, Operator, Orbit, RequestLog, Satellite


def get_db():
    return SessionLocal()


# ---------------------------------------------------------------------------
# stats
# ---------------------------------------------------------------------------
def cmd_stats():
    db = get_db()
    sats = db.execute(select(func.count(Satellite.id))).scalar()
    payloads = db.execute(
        select(func.count(Satellite.id)).where(Satellite.object_type == "PAYLOAD")
    ).scalar()
    launches = db.execute(select(func.count(Launch.id))).scalar()
    operators = db.execute(select(func.count(Operator.id))).scalar()
    real_ops = db.execute(
        select(func.count(Operator.id)).where(Operator.operator_type.isnot(None))
    ).scalar()
    orbits = db.execute(select(func.count(Orbit.id))).scalar()
    keys = db.execute(select(func.count(ApiKey.id))).scalar()
    active_keys = db.execute(
        select(func.count(ApiKey.id)).where(ApiKey.is_active.is_(True))
    ).scalar()
    with_constellation = db.execute(
        select(func.count(Satellite.id)).where(Satellite.constellation.isnot(None))
    ).scalar()

    # Payloads with real operators
    real_op_payloads = db.execute(
        select(func.count(Satellite.id))
        .join(Operator, Satellite.operator_id == Operator.id)
        .where(Satellite.object_type == "PAYLOAD", Operator.operator_type.isnot(None))
    ).scalar()

    # Flagged satellites
    flagged = db.execute(
        select(func.count(Satellite.id)).where(Satellite.source == "flagged")
    ).scalar()

    print("=== Space Data Platform Stats ===\n")
    print(f"Satellites:      {sats:>8}")
    print(f"  Payloads:      {payloads:>8}")
    print(f"  Constellations:{with_constellation:>8}  ({100*with_constellation/payloads:.0f}% of payloads)")
    print(f"  Real operators:{real_op_payloads:>8}  ({100*real_op_payloads/payloads:.0f}% of payloads)")
    print(f"Orbits:          {orbits:>8}")
    print(f"Launches:        {launches:>8}")
    print(f"Operators:       {operators:>8}  ({real_ops} real, {operators - real_ops} country codes)")
    print(f"API keys:        {keys:>8}  ({active_keys} active)")
    if flagged:
        print(f"Flagged:         {flagged:>8}")

    db.close()


# ---------------------------------------------------------------------------
# keys
# ---------------------------------------------------------------------------
def cmd_keys(args):
    if not args:
        print("Usage: keys list | keys create <owner> [--tier <tier>] | keys deactivate <prefix>")
        return

    action = args[0]
    db = get_db()

    if action == "list":
        keys = db.execute(
            select(ApiKey).order_by(ApiKey.created_at.desc())
        ).scalars().all()
        if not keys:
            print("No API keys found.")
            db.close()
            return
        print(f"{'Prefix':<16} {'Owner':<20} {'Tier':<12} {'Active':<8} {'Created'}")
        print("-" * 80)
        for k in keys:
            prefix = k.key_prefix or "???"
            print(f"{prefix}...      {k.owner:<20} {k.tier:<12} "
                  f"{'yes' if k.is_active else 'no':<8} {k.created_at}")

    elif action == "create":
        if len(args) < 2:
            print("Usage: keys create <owner> [--tier free|individual|team]")
            db.close()
            return
        owner = args[1]
        tier = "free"
        if "--tier" in args:
            idx = args.index("--tier")
            if idx + 1 < len(args):
                tier = args[idx + 1]
        if tier not in ("free", "individual", "team"):
            print(f"Invalid tier: {tier}. Must be free, individual, or team.")
            db.close()
            return

        raw_key = secrets.token_hex(32)
        key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
        key_prefix = raw_key[:12]
        api_key = ApiKey(key_hash=key_hash, key_prefix=key_prefix, owner=owner, tier=tier)
        db.add(api_key)
        db.commit()
        print(f"Created API key for {owner} (tier: {tier})")
        print(f"Key: {raw_key}")
        print("\nStore this key securely — it cannot be retrieved later.")

    elif action == "deactivate":
        if len(args) < 2:
            print("Usage: keys deactivate <key_prefix>")
            db.close()
            return
        prefix = args[1]
        key = db.execute(
            select(ApiKey).where(
                ApiKey.key_prefix.startswith(prefix), ApiKey.is_active.is_(True)
            )
        ).scalar()
        if not key:
            print(f"No active key found starting with '{prefix}'")
            db.close()
            return
        key.is_active = False
        db.commit()
        print(f"Deactivated key {key.key_prefix}... (owner: {key.owner})")

    else:
        print(f"Unknown keys action: {action}")

    db.close()


# ---------------------------------------------------------------------------
# search
# ---------------------------------------------------------------------------
def cmd_search(args):
    if not args:
        print("Usage: search <query>  (searches by name, NORAD ID, or constellation)")
        return

    query = " ".join(args)
    db = get_db()

    # Try NORAD ID first
    try:
        norad_id = int(query)
        sat = db.execute(
            select(Satellite).where(Satellite.norad_id == norad_id)
        ).scalar()
        if sat:
            _print_satellite(db, sat)
            db.close()
            return
    except ValueError:
        pass

    # Search by name
    results = db.execute(
        select(Satellite)
        .where(Satellite.name.ilike(f"%{query}%"))
        .order_by(Satellite.name)
        .limit(25)
    ).scalars().all()

    if not results:
        print(f"No satellites found matching '{query}'")
        db.close()
        return

    print(f"Found {len(results)} results (max 25 shown):\n")
    print(f"{'NORAD':<8} {'Name':<30} {'Type':<12} {'Constellation':<20} {'Operator'}")
    print("-" * 95)
    for sat in results:
        op_name = ""
        if sat.operator_id:
            op = db.execute(select(Operator.name).where(Operator.id == sat.operator_id)).scalar()
            op_name = op or ""
        print(f"{sat.norad_id or '':<8} {sat.name:<30} {sat.object_type or '':<12} "
              f"{sat.constellation or '':<20} {op_name}")

    db.close()


def _print_satellite(db, sat):
    """Print detailed info for a single satellite."""
    print(f"\n=== {sat.name} ===\n")
    print(f"  NORAD ID:       {sat.norad_id}")
    print(f"  Intl designator:{sat.intl_designator}")
    print(f"  Object type:    {sat.object_type}")
    print(f"  Status:         {sat.status}")
    print(f"  Purpose:        {sat.purpose or '-'}")
    print(f"  Constellation:  {sat.constellation or '-'}")

    if sat.operator_id:
        op = db.execute(select(Operator).where(Operator.id == sat.operator_id)).scalar()
        if op:
            print(f"  Operator:       {op.name} ({op.operator_type or 'country code'})")

    if sat.orbit:
        o = sat.orbit
        print(f"  Orbit class:    {o.orbit_class}")
        print(f"  Apogee:         {o.apogee_km:.1f} km" if o.apogee_km else "  Apogee:         -")
        print(f"  Perigee:        {o.perigee_km:.1f} km" if o.perigee_km else "  Perigee:        -")
        print(f"  Inclination:    {o.inclination_deg:.1f}°" if o.inclination_deg else "  Inclination:    -")
        print(f"  Period:         {o.period_min:.1f} min" if o.period_min else "  Period:         -")

    if sat.source == "flagged":
        print(f"  ** FLAGGED:     {sat.source_id}")

    print(f"  Updated:        {sat.updated_at}")


# ---------------------------------------------------------------------------
# operator
# ---------------------------------------------------------------------------
def cmd_operator(args):
    if not args:
        print("Usage: operator reassign <norad_id> <operator_name>")
        print("       operator list [--country-only]")
        return

    action = args[0]
    db = get_db()

    if action == "list":
        country_only = "--country-only" in args
        query = (
            select(Operator.name, Operator.operator_type, Operator.country,
                   func.count(Satellite.id))
            .outerjoin(Satellite, Satellite.operator_id == Operator.id)
            .group_by(Operator.id, Operator.name, Operator.operator_type, Operator.country)
            .order_by(func.count(Satellite.id).desc())
        )
        if country_only:
            query = query.where(Operator.operator_type.is_(None))

        rows = db.execute(query).all()
        print(f"{'Operator':<45} {'Type':<12} {'Country':<8} {'Sats'}")
        print("-" * 80)
        for name, otype, country, count in rows:
            print(f"{name:<45} {otype or '-':<12} {country or '-':<8} {count}")

    elif action == "reassign":
        if len(args) < 3:
            print("Usage: operator reassign <norad_id> <operator_name>")
            db.close()
            return
        try:
            norad_id = int(args[1])
        except ValueError:
            print(f"Invalid NORAD ID: {args[1]}")
            db.close()
            return
        operator_name = " ".join(args[2:])

        sat = db.execute(
            select(Satellite).where(Satellite.norad_id == norad_id)
        ).scalar()
        if not sat:
            print(f"No satellite found with NORAD ID {norad_id}")
            db.close()
            return

        # Find or create operator
        op = db.execute(
            select(Operator).where(Operator.name == operator_name)
        ).scalar()
        if not op:
            confirm = input(f"Operator '{operator_name}' doesn't exist. Create it? [y/N] ")
            if confirm.lower() != "y":
                db.close()
                return
            op = Operator(name=operator_name)
            db.add(op)
            db.flush()

        old_op = db.execute(
            select(Operator.name).where(Operator.id == sat.operator_id)
        ).scalar()
        sat.operator_id = op.id
        sat.updated_at = datetime.now(tz=None)
        db.commit()
        print(f"{sat.name}: {old_op} -> {operator_name}")

    else:
        print(f"Unknown operator action: {action}")

    db.close()


# ---------------------------------------------------------------------------
# constellation
# ---------------------------------------------------------------------------
def cmd_constellation(args):
    if not args:
        print("Usage: constellation set <norad_id> <constellation>")
        print("       constellation clear <norad_id>")
        return

    action = args[0]
    db = get_db()

    if action in ("set", "clear"):
        if len(args) < 2:
            print(f"Usage: constellation {action} <norad_id> {'<constellation>' if action == 'set' else ''}")
            db.close()
            return
        try:
            norad_id = int(args[1])
        except ValueError:
            print(f"Invalid NORAD ID: {args[1]}")
            db.close()
            return

        sat = db.execute(
            select(Satellite).where(Satellite.norad_id == norad_id)
        ).scalar()
        if not sat:
            print(f"No satellite found with NORAD ID {norad_id}")
            db.close()
            return

        if action == "set":
            if len(args) < 3:
                print("Usage: constellation set <norad_id> <constellation>")
                db.close()
                return
            new_val = " ".join(args[2:])
            old_val = sat.constellation
            sat.constellation = new_val
            sat.updated_at = datetime.now(tz=None)
            db.commit()
            print(f"{sat.name}: constellation {old_val or '(none)'} -> {new_val}")
        else:  # clear
            old_val = sat.constellation
            sat.constellation = None
            sat.updated_at = datetime.now(tz=None)
            db.commit()
            print(f"{sat.name}: constellation {old_val or '(none)'} -> (cleared)")

    else:
        print(f"Unknown constellation action: {action}")

    db.close()


# ---------------------------------------------------------------------------
# flag / flags
# ---------------------------------------------------------------------------
def cmd_flag(args):
    """Flag a satellite for manual review."""
    if not args or len(args) < 2:
        print("Usage: flag <norad_id> <note>")
        return

    try:
        norad_id = int(args[0])
    except ValueError:
        print(f"Invalid NORAD ID: {args[0]}")
        return

    note = " ".join(args[1:])
    db = get_db()

    sat = db.execute(
        select(Satellite).where(Satellite.norad_id == norad_id)
    ).scalar()
    if not sat:
        print(f"No satellite found with NORAD ID {norad_id}")
        db.close()
        return

    sat.source = "flagged"
    sat.source_id = note
    sat.updated_at = datetime.now(tz=None)
    db.commit()
    print(f"Flagged {sat.name} (NORAD {norad_id}): {note}")
    db.close()


def cmd_flags(args):
    """List or resolve flagged satellites."""
    db = get_db()
    action = args[0] if args else "list"

    if action == "list":
        flagged = db.execute(
            select(Satellite)
            .where(Satellite.source == "flagged")
            .order_by(Satellite.updated_at.desc())
        ).scalars().all()
        if not flagged:
            print("No flagged satellites.")
            db.close()
            return
        print(f"{'NORAD':<8} {'Name':<30} {'Note'}")
        print("-" * 70)
        for sat in flagged:
            print(f"{sat.norad_id or '':<8} {sat.name:<30} {sat.source_id or ''}")

    elif action == "resolve":
        if len(args) < 2:
            print("Usage: flags resolve <norad_id>")
            db.close()
            return
        try:
            norad_id = int(args[1])
        except ValueError:
            print(f"Invalid NORAD ID: {args[1]}")
            db.close()
            return

        sat = db.execute(
            select(Satellite).where(
                Satellite.norad_id == norad_id, Satellite.source == "flagged"
            )
        ).scalar()
        if not sat:
            print(f"No flagged satellite with NORAD ID {norad_id}")
            db.close()
            return

        sat.source = "space_track"
        sat.source_id = str(norad_id)
        sat.updated_at = datetime.now(tz=None)
        db.commit()
        print(f"Resolved flag on {sat.name} (NORAD {norad_id})")

    else:
        print(f"Unknown flags action: {action}")

    db.close()


# ---------------------------------------------------------------------------
# usage
# ---------------------------------------------------------------------------
def cmd_usage(args):
    """Show API usage stats from request log."""
    days = 7
    user_filter = None

    # Parse args
    i = 0
    while i < len(args):
        if args[i] == "--days" and i + 1 < len(args):
            days = int(args[i + 1])
            i += 2
        elif args[i] == "--user" and i + 1 < len(args):
            user_filter = args[i + 1]
            i += 2
        else:
            i += 1

    db = get_db()
    since = datetime.utcnow() - __import__("datetime").timedelta(days=days)

    base = select(RequestLog).where(RequestLog.created_at >= since)
    if user_filter:
        base = base.where(RequestLog.owner.ilike(f"%{user_filter}%"))

    logs = db.execute(base.order_by(RequestLog.created_at.desc())).scalars().all()

    if not logs:
        print(f"No requests in the last {days} days.")
        db.close()
        return

    # Summary by user
    print(f"=== API Usage (last {days} days) ===\n")

    user_counts = {}
    endpoint_counts = {}
    for log in logs:
        owner = log.owner or "unknown"
        user_counts[owner] = user_counts.get(owner, 0) + 1
        endpoint_counts[log.endpoint] = endpoint_counts.get(log.endpoint, 0) + 1

    print("Requests by user:")
    print(f"  {'User':<25} {'Tier':<12} {'Requests'}")
    print(f"  {'-'*25} {'-'*12} {'-'*8}")
    # Get tier for each user
    user_tiers = {}
    for log in logs:
        if log.owner:
            user_tiers[log.owner] = log.tier or "—"
    for owner, count in sorted(user_counts.items(), key=lambda x: -x[1]):
        tier = user_tiers.get(owner, "—")
        print(f"  {owner:<25} {tier:<12} {count}")

    print(f"\nRequests by endpoint:")
    print(f"  {'Endpoint':<40} {'Requests'}")
    print(f"  {'-'*40} {'-'*8}")
    for endpoint, count in sorted(endpoint_counts.items(), key=lambda x: -x[1]):
        print(f"  {endpoint:<40} {count}")

    # Recent requests detail
    print(f"\nRecent requests (last 20):")
    print(f"  {'Time':<20} {'User':<20} {'Endpoint':<30} {'Params'}")
    print(f"  {'-'*20} {'-'*20} {'-'*30} {'-'*30}")
    for log in logs[:20]:
        ts = log.created_at.strftime("%Y-%m-%d %H:%M") if log.created_at else "—"
        owner = (log.owner or "—")[:19]
        params = (log.query_params or "—")[:30]
        print(f"  {ts:<20} {owner:<20} {log.endpoint:<30} {params}")

    print(f"\nTotal: {len(logs)} requests from {len(user_counts)} users")
    db.close()


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------
COMMANDS = {
    "stats": lambda args: cmd_stats(),
    "keys": cmd_keys,
    "search": cmd_search,
    "operator": cmd_operator,
    "constellation": cmd_constellation,
    "flag": cmd_flag,
    "flags": cmd_flags,
    "usage": cmd_usage,
}


def main():
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help", "help"):
        print(__doc__)
        return

    cmd = sys.argv[1]
    args = sys.argv[2:]

    if cmd not in COMMANDS:
        print(f"Unknown command: {cmd}")
        print(f"Available commands: {', '.join(COMMANDS.keys())}")
        return

    COMMANDS[cmd](args)


if __name__ == "__main__":
    main()
