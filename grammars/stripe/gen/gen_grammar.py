"""Generate grammars/stripe/stripe.grammar.toml.

Usage (from grammars/stripe/):
  python3 -I gen/parse_specs.py <stripe-cli>/pkg/cmd/resources/specs_gen.go > /tmp/specs.json
  python3 -I gen/gen_grammar.py /tmp/specs.json gen/head.toml > stripe.grammar.toml

<specs.json> comes from parse_specs.py over stripe-cli v1.55.10 pkg/cmd/resources/specs_gen.go.
<head.toml> is the hand-written part (header, effects, globals, non-resource commands).
The generated part is one [shell.*] table per resource operation, with each request parameter
that stripe-cli registers as a flag (operation.go::NewOperationCmd), plus the shared request flags
(requests/base.go::InitFlags).
"""
import json
import re
import sys

specs = json.load(open(sys.argv[1]))
head = open(sys.argv[2]).read()

W, D, M = "write_data", "delete_data", "move_money"

# (spec var, command words, extra action effects); a resource with `_` in its name cannot be a
# Box command word, so payment_intents, webhook_endpoints, payment_methods, ... are left out.
OPS = [
    ("V1BalanceRetrieve", "balance retrieve", []),
    ("V1CustomersCreate", "customers create", [W]),
    ("V1CustomersDelete", "customers delete", [D]),
    ("V1CustomersList", "customers list", []),
    ("V1CustomersRetrieve", "customers retrieve", []),
    ("V1CustomersSearch", "customers search", []),
    ("V1CustomersUpdate", "customers update", [W]),
    ("V1ChargesCapture", "charges capture", [W, M]),
    ("V1ChargesCreate", "charges create", [W, M]),
    ("V1ChargesList", "charges list", []),
    ("V1ChargesRetrieve", "charges retrieve", []),
    ("V1ChargesSearch", "charges search", []),
    ("V1ChargesUpdate", "charges update", [W]),
    ("V1RefundsCancel", "refunds cancel", [W]),
    ("V1RefundsCreate", "refunds create", [W, M]),
    ("V1RefundsList", "refunds list", []),
    ("V1RefundsRetrieve", "refunds retrieve", []),
    ("V1RefundsUpdate", "refunds update", [W]),
    ("V1SubscriptionsCancel", "subscriptions cancel", [D, M]),
    ("V1SubscriptionsCreate", "subscriptions create", [W, M]),
    ("V1SubscriptionsList", "subscriptions list", []),
    ("V1SubscriptionsMigrate", "subscriptions migrate", [W]),
    ("V1SubscriptionsPause", "subscriptions pause", [W, M]),
    ("V1SubscriptionsResume", "subscriptions resume", [W, M]),
    ("V1SubscriptionsRetrieve", "subscriptions retrieve", []),
    ("V1SubscriptionsSearch", "subscriptions search", []),
    ("V1SubscriptionsUpdate", "subscriptions update", [W, M]),
    ("V1InvoicesCreate", "invoices create", [W, M]),
    ("V1InvoicesDelete", "invoices delete", [D]),
    ("V1InvoicesList", "invoices list", []),
    ("V1InvoicesPay", "invoices pay", [W, M]),
    ("V1InvoicesRetrieve", "invoices retrieve", []),
    ("V1InvoicesSearch", "invoices search", []),
    ("V1InvoicesUpdate", "invoices update", [W, M]),
    ("V1ProductsCreate", "products create", [W]),
    ("V1ProductsDelete", "products delete", [D]),
    ("V1ProductsList", "products list", []),
    ("V1ProductsRetrieve", "products retrieve", []),
    ("V1ProductsSearch", "products search", []),
    ("V1ProductsUpdate", "products update", [W]),
    ("V1PricesCreate", "prices create", [W]),
    ("V1PricesList", "prices list", []),
    ("V1PricesRetrieve", "prices retrieve", []),
    ("V1PricesSearch", "prices search", []),
    ("V1PricesUpdate", "prices update", [W]),
    ("V1CheckoutSessionsCreate", "checkout sessions create", [W]),
    ("V1CheckoutSessionsExpire", "checkout sessions expire", [W]),
    ("V1CheckoutSessionsList", "checkout sessions list", []),
    ("V1CheckoutSessionsRetrieve", "checkout sessions retrieve", []),
    ("V1CheckoutSessionsUpdate", "checkout sessions update", [W]),
    ("V1EventsList", "events list", []),
    ("V1EventsRetrieve", "events retrieve", []),
    # events resend is hand-defined in resource/events_resend.go
    ("EventsResend", "events resend", [W]),
]
specs["EventsResend"] = {
    "name": "resend", "path": "/v1/events/{event}/retry", "method": "POST",
    "params": {"account": "string", "webhook_endpoint": "string"},
}

# Request parameters that add an effect of their own.
PARAM_ADDS = {
    ("EventsResend", "webhook_endpoint"): ["forward_events"],
}
# `-d` can send any request parameter, so it carries the effects of the parameters above.
DATA_ADDS = {
    "EventsResend": ["forward_events"],
}
# A comment above an action, for an effect choice that a reader could question.
NOTES = {
    "V1InvoicesCreate": "`auto_advance` (a flag or `-d`) lets Stripe finalize and collect the invoice.",
    "V1InvoicesUpdate": "`auto_advance` (a flag or `-d`) lets Stripe finalize and collect the invoice.",
    "V1SubscriptionsPause": "`invoicing_behavior=invoice` bills the open debits at once.",
    "V1SubscriptionsCancel": "An HTTP DELETE; `invoice_now` can bill a final invoice.",
    "V1RefundsCancel": "Stops a pending refund, so the money stays in the account: no `move_money`.",
    "EventsResend": "Sends the event again, to the CLI or to the endpoint `--webhook-endpoint` names.",
}

GLOBAL_KEYS = {"api_key", "color", "config", "device_name", "log_level", "project_name"}
RESERVED = {"program", "program_path", "cwd", "args", "effects", "credential_reads"}
CEDAR = {"true", "false", "if", "then", "else", "in", "is", "like", "has"}


def q(xs):
    return "[" + ", ".join(json.dumps(x) for x in xs) + "]"


def opt(flags, value=None, repeated=False, adds=(), removes=()):
    parts = [f"flag = {q(flags)}"]
    if value:
        parts.append(f'value = "{value}"')
    if repeated:
        parts.append("repeated = true")
    if adds:
        parts.append(f"adds = {q(sorted(adds))}")
    if removes:
        parts.append(f"removes = {q(sorted(removes))}")
    return "{ " + ", ".join(parts) + " }"


def base_options(method, own_flags, data_adds=()):
    """requests/base.go::InitFlags, as an operation command registers it."""
    rows = []
    if "confirm" not in own_flags:
        rows.append(("confirm", opt(["-c", "--confirm"], adds=["skip_prompt"] if method == "DELETE" else [])))
    rows += [
        ("dark_style", opt(["--dark-style"])),
        ("data", opt(["-d", "--data"], "required", True, data_adds)),
        ("dry_run", opt(["--dry-run"], removes=[W, D, M])),
        ("expand", opt(["-e", "--expand"], "required", True)),
        ("idempotency", opt(["-i", "--idempotency"], "required")),
        ("live", opt(["--live"], adds=["live_mode"])),
        ("show_headers", opt(["-s", "--show-headers"])),
        ("stripe_account", opt(["--stripe-account"], "required", adds=["connected_account"])),
        ("stripe_context", opt(["--stripe-context"], "required", adds=["connected_account"])),
        ("stripe_version", opt(["-v", "--stripe-version"], "required")),
    ]
    if method == "GET":
        for key, short in (("limit", "-l"), ("starting_after", "-a"), ("ending_before", "-b")):
            if key.replace("_", "-") not in own_flags:
                rows.append((key, opt([short, "--" + key.replace("_", "-")], "required")))
    return rows


out = [head.rstrip("\n"), "", "# " + "-" * 98,
       "# Resource commands. Generated from stripe-cli v1.55.10 pkg/cmd/resources/specs_gen.go: one",
       "# option per request parameter that NewOperationCmd registers as a flag (object parameters get",
       "# none), with the dotted-hyphen spelling the help prints. The shared request flags come from",
       "# requests/base.go::InitFlags. `--request-header`/`-H` and the hidden `--api-base` are left out.",
       "# " + "-" * 98]
for var, words, adds in OPS:
    s = specs[var]
    method = s["method"]
    url_params = re.findall(r"\{([^}]+)\}", s["path"])
    flags = {}
    for prop, typ in sorted(s["params"].items()):
        if typ not in ("array", "string", "clearable_object", "number", "integer", "boolean"):
            continue
        flag = prop.replace("_", "-")
        key = prop.replace(".", "_").replace("-", "_")
        if key in GLOBAL_KEYS or key in RESERVED or key in CEDAR:
            raise SystemExit(f"{var}: parameter {prop} needs a renamed key")
        if typ == "array":
            o = opt(["--" + flag], "required", True, PARAM_ADDS.get((var, prop), []))
        elif typ == "boolean":
            # pflag Bool: bare or `=true|false`; `--x true` is rewritten by NormalizeBooleanRequestArgs.
            o = opt(["--" + flag], "optional", adds=PARAM_ADDS.get((var, prop), []))
        else:
            o = opt(["--" + flag], "required", adds=PARAM_ADDS.get((var, prop), []))
        if key in flags:
            raise SystemExit(f"{var}: key collision {key}")
        flags[key] = (flag, o)
    own = {f for f, _ in flags.values()}
    rows = base_options(method, own, DATA_ADDS.get(var, [])) + [(k, o) for k, (_, o) in flags.items()]
    keys = [k for k, _ in rows]
    if len(keys) != len(set(keys)):
        raise SystemExit(f"{var}: duplicate keys")
    for u in url_params:
        if u in keys or u in GLOBAL_KEYS:
            raise SystemExit(f"{var}: operand {u} collides")
    action = words.replace(" ", "_")
    operands = " ".join(f"<{u}>" for u in url_params)
    usage = f"stripe [global options] {words} [options]" + (f" {operands}" if operands else "")
    effects = ["network"] + adds
    out += ["", f"# {method} {s['path']}"] + ([f"# {NOTES[var]}"] if var in NOTES else []) + [f"[shell.{action}]", f'usage = "{usage}"',
            f"adds  = {q(sorted(effects))}"]
    for k, o in sorted(rows):
        out.append(f"options.{k} = {o}")
print("\n".join(out))
