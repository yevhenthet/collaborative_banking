from fastapi.templating import Jinja2Templates
from .i18n import (
    t, diff_label_fn, type_label_fn, bloom_hint_fn, bloom_detail_fn,
    type_hint_fn, type_detail_fn, crit_opts_fn, crit_anchors_fn, get_lang_fn, org_setting_fn,
)

templates = Jinja2Templates(directory="templates")

templates.env.globals["t"]            = t
templates.env.globals["diff_label"]   = diff_label_fn
templates.env.globals["bloom_hint"]   = bloom_hint_fn
templates.env.globals["bloom_detail"] = bloom_detail_fn
templates.env.globals["type_label"]   = type_label_fn
templates.env.globals["type_hint"]    = type_hint_fn
templates.env.globals["type_detail"]  = type_detail_fn
templates.env.globals["crit_opts"]    = crit_opts_fn
templates.env.globals["crit_anchors"] = crit_anchors_fn
templates.env.globals["get_lang"]     = get_lang_fn
templates.env.globals["org_setting"]  = org_setting_fn
