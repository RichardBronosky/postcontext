import os

# Tests must never drive a real browser.
os.environ["POSTCONTEXT_BROWSER"] = "0"
