"""Generate gws.grammar.toml. From grammars/gws: python3 -I gen/gen_grammar.py > gws.grammar.toml"""
import itertools
import re

R, W, D, T, S, SEND = "read", "write", "delete", "trash", "share", "send"
ADDS = {R: ["read_data"], W: ["write_data"], D: ["delete_data"], T: ["trash_data"],
        S: ["share_external"], SEND: ["send_email"]}

def variants(word):
    return ["*" + "".join(p) + "*" for p in itertools.product(*[(c.lower(), c.upper()) for c in word])]

ANYONE = variants("anyone") + ["*\\u*"]
NOTIFY = ["*sendUpdates*", "*sendNotifications*", "*send_updates*", "*send_notifications*", "*\\u*"]
PUBLISH = variants("publish") + ["*\\u*"]
PARENTS = variants("parents") + ["*\\u*"]
TRASH = variants("trash") + ["*\\u*"]
INHERIT = variants("inherit")
SHARE_RULES = variants("writers") + variants("requires") + variants("download") + ["*\\u*"]
RESTRICT = variants("restrict") + ["*\\u*"]
TRANSFER = variants("transfer") + ["*\\u*"]
AUDIENCE = PARENTS + INHERIT

# Per action: extra always-adds, and `when` entries on --params / --json as (effects, patterns).
SPECIAL = {
    "drive files copy":         {"json": [(["share_external"], AUDIENCE), (["change_sharing_rules"], SHARE_RULES)]},
    "drive files create":       {"json": [(["share_external"], AUDIENCE), (["change_sharing_rules"], SHARE_RULES)]},
    "drive files update":       {"params": [(["share_external"], PARENTS)],
                                 "json": [(["share_external"], AUDIENCE), (["change_sharing_rules"], SHARE_RULES)]},
    "drive drives create":      {"json": [(["change_sharing_rules"], RESTRICT)]},
    "drive drives update":      {"json": [(["change_sharing_rules"], RESTRICT)]},
    "drive permissions create": {"adds": ["send_email"], "json": [(["make_public"], ANYONE)]},
    "drive permissions update": {"adds": ["make_public"], "params": [(["send_email"], TRANSFER)]},
    "drive revisions update":   {"json": [(["make_public", "share_external"], PUBLISH)]},
    "gmail users messages modify": {"json": [(["trash_data"], TRASH)]},
    "gmail users threads modify":  {"json": [(["trash_data"], TRASH)]},
    "gmail users messages batchModify": {"json": [(["trash_data"], TRASH)]},
    "calendar acl insert": {"adds": ["make_public", "send_email"]},
    "calendar acl patch":  {"adds": ["make_public", "send_email"]},
    "calendar acl update": {"adds": ["make_public", "send_email"]},
}
for w in ["insert", "patch", "update", "move", "delete"]:
    SPECIAL["calendar events " + w] = {"params": [(["send_email"], NOTIFY)]}
SPECIAL["calendar events move"]["adds"] = ["share_external"]

# (words, kind, has_body, has_upload, extra)
# extra: unused; per-action effects are in SPECIAL
FAMILIES = [
  ("Drive v3", [
    ("drive about get", R, 0, 0, None),
    ("drive files list", R, 0, 0, None),
    ("drive files get", R, 0, 0, None),
    ("drive files export", R, 0, 0, None),
    ("drive files download", R, 0, 0, None),
    ("drive files copy", W, 1, 0, None),
    ("drive files create", W, 1, 1, None),
    ("drive files update", W, 1, 1, None),
    ("drive files delete", D, 0, 0, None),
    ("drive files emptyTrash", D, 0, 0, None),
    ("drive permissions list", R, 0, 0, None),
    ("drive permissions get", R, 0, 0, None),
    ("drive permissions create", S, 1, 0, None),
    ("drive permissions update", S, 1, 0, None),
    ("drive permissions delete", D, 0, 0, None),
    ("drive drives list", R, 0, 0, None),
    ("drive drives get", R, 0, 0, None),
    ("drive drives create", W, 1, 0, None),
    ("drive drives update", W, 1, 0, None),
    ("drive drives hide", W, 0, 0, None),
    ("drive drives unhide", W, 0, 0, None),
    ("drive drives delete", D, 0, 0, None),
    ("drive comments list", R, 0, 0, None),
    ("drive comments get", R, 0, 0, None),
    ("drive comments create", W, 1, 0, None),
    ("drive comments update", W, 1, 0, None),
    ("drive comments delete", D, 0, 0, None),
    ("drive replies list", R, 0, 0, None),
    ("drive replies get", R, 0, 0, None),
    ("drive replies create", W, 1, 0, None),
    ("drive replies update", W, 1, 0, None),
    ("drive replies delete", D, 0, 0, None),
    ("drive revisions list", R, 0, 0, None),
    ("drive revisions get", R, 0, 0, None),
    ("drive revisions update", W, 1, 0, None),
    ("drive revisions delete", D, 0, 0, None),
    ("drive changes list", R, 0, 0, None),
  ]),
  ("Gmail v1", [
    ("gmail users messages list", R, 0, 0, None),
    ("gmail users messages get", R, 0, 0, None),
    ("gmail users messages send", SEND, 1, 1, None),
    ("gmail users messages modify", W, 1, 0, None),
    ("gmail users messages import", W, 1, 1, None),
    ("gmail users messages insert", W, 1, 1, None),
    ("gmail users messages trash", T, 0, 0, None),
    ("gmail users messages untrash", W, 0, 0, None),
    ("gmail users messages delete", D, 0, 0, None),
    ("gmail users messages batchModify", W, 1, 0, None),
    ("gmail users messages batchDelete", D, 1, 0, None),
    ("gmail users messages attachments get", R, 0, 0, None),
    ("gmail users drafts list", R, 0, 0, None),
    ("gmail users drafts get", R, 0, 0, None),
    ("gmail users drafts create", W, 1, 1, None),
    ("gmail users drafts update", W, 1, 1, None),
    ("gmail users drafts send", SEND, 1, 1, None),
    ("gmail users drafts delete", D, 0, 0, None),
    ("gmail users threads list", R, 0, 0, None),
    ("gmail users threads get", R, 0, 0, None),
    ("gmail users threads modify", W, 1, 0, None),
    ("gmail users threads trash", T, 0, 0, None),
    ("gmail users threads untrash", W, 0, 0, None),
    ("gmail users threads delete", D, 0, 0, None),
    ("gmail users labels list", R, 0, 0, None),
    ("gmail users labels get", R, 0, 0, None),
    ("gmail users labels create", W, 1, 0, None),
    ("gmail users labels patch", W, 1, 0, None),
    ("gmail users labels update", W, 1, 0, None),
    ("gmail users labels delete", D, 0, 0, None),
    ("gmail users history list", R, 0, 0, None),
    ("gmail users settings filters list", R, 0, 0, None),
    ("gmail users settings filters get", R, 0, 0, None),
    ("gmail users getProfile", R, 0, 0, None),
  ]),
  ("Calendar v3", [
    ("calendar events list", R, 0, 0, None),
    ("calendar events get", R, 0, 0, None),
    ("calendar events instances", R, 0, 0, None),
    ("calendar events insert", W, 1, 0, None),
    ("calendar events patch", W, 1, 0, None),
    ("calendar events update", W, 1, 0, None),
    ("calendar events move", W, 0, 0, None),
    ("calendar events import", W, 1, 0, None),
    ("calendar events delete", D, 0, 0, None),
    ("calendar calendars get", R, 0, 0, None),
    ("calendar calendars insert", W, 1, 0, None),
    ("calendar calendars patch", W, 1, 0, None),
    ("calendar calendars update", W, 1, 0, None),
    ("calendar calendars clear", D, 0, 0, None),
    ("calendar calendars delete", D, 0, 0, None),
    ("calendar acl list", R, 0, 0, None),
    ("calendar acl get", R, 0, 0, None),
    ("calendar acl insert", S, 1, 0, None),
    ("calendar acl patch", S, 1, 0, None),
    ("calendar acl update", S, 1, 0, None),
    ("calendar acl delete", D, 0, 0, None),
    ("calendar freebusy query", R, 1, 0, None),
    ("calendar colors get", R, 0, 0, None),
    ("calendar settings list", R, 0, 0, None),
    ("calendar settings get", R, 0, 0, None),
    ("calendar calendarList list", R, 0, 0, None),
    ("calendar calendarList get", R, 0, 0, None),
  ]),
  ("Sheets v4", [
    ("sheets spreadsheets get", R, 0, 0, None),
    ("sheets spreadsheets create", W, 1, 0, None),
    ("sheets spreadsheets batchUpdate", W, 1, 0, None),
    ("sheets spreadsheets values get", R, 0, 0, None),
    ("sheets spreadsheets values batchGet", R, 0, 0, None),
    ("sheets spreadsheets values append", W, 1, 0, None),
    ("sheets spreadsheets values update", W, 1, 0, None),
    ("sheets spreadsheets values clear", D, 1, 0, None),
  ]),
  ("Docs v1", [
    ("docs documents get", R, 0, 0, None),
    ("docs documents create", W, 1, 0, None),
    ("docs documents batchUpdate", W, 1, 0, None),
  ]),
]

DRY = ["read_data", "write_data", "delete_data", "trash_data", "send_email",
       "share_external", "make_public", "change_sharing_rules", "upload_file", "write_local_file"]

def tlist(xs):
    return "[" + ", ".join('"' + x + '"' for x in xs) + "]"

def pats(xs, per=8, indent="    "):
    lines = []
    for i in range(0, len(xs), per):
        lines.append(indent + ", ".join("'" + x + "'" for x in xs[i:i+per]) + ",")
    return "\n".join(lines)

out = []
p = out.append
p(open(__file__.replace("gen_grammar.py", "header.toml")).read().rstrip("\n"))
for title, actions in FAMILIES:
    p("")
    p("# " + "-" * 98)
    p(f"# {title}")
    p("# " + "-" * 98)
    for words, kind, body, upload, extra in actions:
        name = re.sub(r"([a-z])([A-Z])", r"\1_\2", words).lower().replace(" ", "_").replace("-", "_")
        sp = SPECIAL.get(words, {})
        adds = list(ADDS[kind]) + sp.get("adds", [])
        p("")
        p(f"[shell.{name}]")
        p(f'usage = "gws {words} [options]"')
        p(f"adds  = {tlist(adds)}")
        def opt(key, flag, whens):
            if not whens:
                p(f'options.{key:<9} = {{ flag = ["{flag}"], value = "required" }}')
                return
            p(f'options.{key} = {{ flag = ["{flag}"], value = "required", when = [')
            for effs, pt in whens:
                p(f"  {{ adds = {tlist(effs)}, like = [")
                p(pats(pt))
                p("  ] },")
            p("] }")
        opt("params", "--params", sp.get("params"))
        if body:
            opt("json", "--json", sp.get("json"))
        if upload:
            p('options.upload    = { flag = ["--upload"], value = "required", adds = ["upload_file"] }')
            p('options.upload_content_type = { flag = ["--upload-content-type"], value = "required" }')
        p('options.output    = { flag = ["-o", "--output"], value = "required", adds = ["write_local_file"] }')
        p('options.format    = { flag = ["--format"], value = "required" }')
        p('options.page_all  = { flag = ["--page-all"] }')
        p('options.page_limit = { flag = ["--page-limit"], value = "required" }')
        p('options.page_delay = { flag = ["--page-delay"], value = "required" }')
        p('options.dry_run   = { flag = ["--dry-run"], removes = ' + tlist(DRY) + ' }')
print("\n".join(out) + "\n")
