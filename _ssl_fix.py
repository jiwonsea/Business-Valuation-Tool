"""Fix curl_cffi SSL on Windows with non-ASCII user paths.

curl_cffi reads certifi.where() which returns a path under %APPDATA%.
When the Windows username contains non-ASCII characters (e.g. Korean),
curl_cffi fails to open the CA bundle.  Setting CURL_CA_BUNDLE to an
ASCII-safe copy of the certificate file resolves this.

Import this module early in any entry point (cli.py, app.py, etc.).
"""

import os
import sys


def apply() -> None:
    if os.environ.get("CURL_CA_BUNDLE"):
        return

    if sys.platform != "win32":
        return

    try:
        import certifi
    except ImportError:
        return

    src = certifi.where()
    try:
        src.encode("ascii")
        return  # path is ASCII-safe
    except UnicodeEncodeError:
        pass

    dst_dir = os.path.join(os.environ.get("ProgramData", r"C:\ProgramData"), "ssl")
    dst = os.path.join(dst_dir, "cacert.pem")

    if not os.path.exists(dst):
        import shutil
        os.makedirs(dst_dir, exist_ok=True)
        shutil.copy2(src, dst)

    os.environ["CURL_CA_BUNDLE"] = dst


apply()
