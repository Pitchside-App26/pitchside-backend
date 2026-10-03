import re
import subprocess
import shutil

import pytest

from football_goals import betslip, run_report


def test_script_embeds_bookmakers_and_defaults():
    js = betslip.script(run_report.load_config())
    assert '"defaults": {"o15": "SpreadEx", "gibh": "Sky Bet"}' in js
    assert "BoyleSports" in js and "__CFG__" not in js


@pytest.mark.skipif(not shutil.which("node"), reason="node not installed")
def test_script_is_valid_javascript(tmp_path):
    """A stray quote once broke the whole slip; make the browser's parser check it."""
    js = re.sub(r"^<script>|</script>$", "", betslip.script(run_report.load_config()).strip())
    f = tmp_path / "s.js"
    f.write_text(js)
    r = subprocess.run(["node", "--check", str(f)], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr


@pytest.mark.skipif(not shutil.which("node"), reason="node not installed")
def test_other_page_scripts_are_valid_javascript(tmp_path):
    from football_goals import render, update_button
    for name, html in (("app", render.APP_JS), ("update", update_button.script())):
        js = html[html.index("<script>") + 8:html.rindex("</script>")]
        f = tmp_path / f"{name}.js"
        f.write_text(js)
        r = subprocess.run(["node", "--check", str(f)], capture_output=True, text=True)
        assert r.returncode == 0, (name, r.stderr)
