#!/usr/bin/with-contenv bash
# -------------------------------------------------------------------
# RPyC server service script for gmag11/metatrader5_vnc.
#
# Mounted into /custom-cont-init.d/ -- runs once during container
# init. Sets up an s6 supervised service that runs an RPyC
# SlaveService on Wine Python 64-bit, allowing the backend to
# remotely call MetaTrader5 Python API functions.
#
# Also pins rpyc==5.2.3 in native Python to prevent the image's
# built-in mt5linux server from breaking version compatibility.
# -------------------------------------------------------------------

set -euo pipefail

WINE_PREFIX="/config/.wine"
WINE_PYTHON_64="${WINE_PREFIX}/drive_c/Python39-64/python.exe"
WINE_PYTHON_32="${WINE_PREFIX}/drive_c/Program Files (x86)/Python39-32/python.exe"
RPYC_PORT=8001
SVC_DIR="/etc/services.d/rpyc"

log() {
    echo "[start-rpyc] $(date '+%Y-%m-%d %H:%M:%S') $*"
}

# ---- 1. Wait for Wine prefix -----------------------------------------
log "Waiting for Wine prefix ..."
MAX_WAIT=300
WAITED=0
while [ ! -d "${WINE_PREFIX}/drive_c" ]; do
    if [ "$WAITED" -ge "$MAX_WAIT" ]; then
        log "ERROR: Wine prefix not ready after ${MAX_WAIT}s -- aborting."
        exit 1
    fi
    sleep 3
    WAITED=$((WAITED + 3))
done
log "Wine drive_c present (waited ${WAITED}s)."

# ---- 2. Pin rpyc in native Python (prevent 6.x) ----------------------
log "Pinning rpyc==5.2.3 and plumbum==1.7.0 in native Python ..."
pip3 install --break-system-packages --quiet 'rpyc==5.2.3' 'plumbum==1.7.0' 2>&1 \
    | while IFS= read -r line; do log "  pip3: ${line}"; done || true

# ---- 3. Determine which Wine Python to use ----------------------------
if [ -f "${WINE_PYTHON_64}" ]; then
    WINE_PYTHON="${WINE_PYTHON_64}"
    log "Using 64-bit Wine Python."
elif [ -f "${WINE_PYTHON_32}" ]; then
    WINE_PYTHON="${WINE_PYTHON_32}"
    log "Using 32-bit Wine Python."
else
    log "ERROR: No Wine Python found. Install Python in Wine first."
    exit 1
fi

# ---- 4. Ensure dependencies in Wine Python ----------------------------
log "Checking Wine Python dependencies ..."
WINEPREFIX="${WINE_PREFIX}" WINEDEBUG="-all" wine "${WINE_PYTHON}" -m pip install --quiet \
    'rpyc==5.2.3' 'numpy<2' 'MetaTrader5==5.0.36' 2>&1 \
    | while IFS= read -r line; do log "  wine-pip: ${line}"; done || true
log "Dependencies checked."

# ---- 5. Create s6 service directory for RPyC --------------------------
log "Creating s6 service for RPyC at ${SVC_DIR} ..."
mkdir -p "${SVC_DIR}"

cat > "${SVC_DIR}/run" <<RUNEOF
#!/usr/bin/with-contenv bash
# s6 service: RPyC ThreadedServer on port ${RPYC_PORT}
# s6 will restart this automatically if it exits.

# Wait for MT5 terminal to start
sleep 10

exec s6-setuidgid abc \\
    env WINEPREFIX=${WINE_PREFIX} WINEDEBUG=-all \\
    wine '${WINE_PYTHON}' -u -c "
from rpyc.utils.server import ThreadedServer
from rpyc.core.service import SlaveService
import sys

print('[rpyc-svc] Starting RPyC SlaveService on 0.0.0.0:${RPYC_PORT}', flush=True)
print(f'[rpyc-svc] Python {sys.version}', flush=True)
t = ThreadedServer(
    SlaveService,
    port=${RPYC_PORT},
    hostname='0.0.0.0',
    protocol_config={
        'allow_all_attrs': True,
        'allow_public_attrs': True,
    },
)
t.start()
"
RUNEOF

chmod +x "${SVC_DIR}/run"

log "s6 RPyC service created. It will start when s6 scans for new services."
exit 0
