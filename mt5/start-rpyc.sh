#!/usr/bin/with-contenv bash
# -------------------------------------------------------------------
# RPyC server bootstrap for gmag11/metatrader5_vnc.
#
# Mounted into /custom-cont-init.d/ — runs once during container init.
#
# Creates an s6 supervised service that:
#   - Waits for Wine Python to exist
#   - Kills any process on port 8001 (the image's broken [7/7] attempt)
#   - Starts our own RPyC SlaveService on port 8001
#
# Package versions (rpyc, numpy, plumbum) are handled by
# PIP_CONSTRAINT=/etc/pip-constraints.txt mounted from pip-constraints.txt.
# No wine pip installs needed here — the constraint file covers both
# native and Wine pip.
#
# NOTE: The base image's [7/7] step will fail because mt5linux 1.0.x
# removed the -w CLI flag. This is harmless.
# -------------------------------------------------------------------

SVC_DIR="/etc/services.d/rpyc"

echo "[start-rpyc] Creating s6 service at ${SVC_DIR} ..."
mkdir -p "${SVC_DIR}"

# The s6 run script — runs after image init completes
cat > "${SVC_DIR}/run" <<'RUNEOF'
#!/usr/bin/with-contenv bash

WINE_PREFIX="/config/.wine"
RPYC_PORT=8001

log() {
    echo "[rpyc-svc] $(date '+%Y-%m-%d %H:%M:%S') $*"
}

# ---- 1. Wait for Wine Python to exist --------------------------------
log "Waiting for Wine Python ..."
WINE_PYTHON=""
for i in $(seq 1 120); do
    if [ -f "${WINE_PREFIX}/drive_c/Python39-64/python.exe" ]; then
        WINE_PYTHON="${WINE_PREFIX}/drive_c/Python39-64/python.exe"
        break
    elif [ -f "${WINE_PREFIX}/drive_c/Program Files (x86)/Python39-32/python.exe" ]; then
        WINE_PYTHON="${WINE_PREFIX}/drive_c/Program Files (x86)/Python39-32/python.exe"
        break
    fi
    sleep 5
done

if [ -z "$WINE_PYTHON" ]; then
    log "ERROR: Wine Python not found after 600s. Retrying in 30s ..."
    sleep 30
    exit 1  # s6 will restart us
fi
log "Found: ${WINE_PYTHON}"

# ---- 2. Wait for MetaTrader5 to be importable ------------------------
# Poll until Wine Python can import MetaTrader5 successfully.
# PIP_CONSTRAINT ensures numpy<2 so the import won't fail on numpy.
log "Waiting for MetaTrader5 to be importable ..."
for i in $(seq 1 120); do
    s6-setuidgid abc env WINEPREFIX="${WINE_PREFIX}" WINEDEBUG="-all" \
        wine "${WINE_PYTHON}" -c "import MetaTrader5" >/dev/null 2>&1 && break
    sleep 5
done

# ---- 3. Kill anything on port 8001 (broken [7/7] or stale server) ----
fuser -k ${RPYC_PORT}/tcp 2>/dev/null && log "Killed stale process on :${RPYC_PORT}" || true
sleep 2

# ---- 4. Start RPyC SlaveService --------------------------------------
log "Starting RPyC SlaveService on 0.0.0.0:${RPYC_PORT} ..."
exec s6-setuidgid abc \
    env WINEPREFIX="${WINE_PREFIX}" WINEDEBUG=-all \
    wine "${WINE_PYTHON}" -u -c "
from rpyc.utils.server import ThreadedServer
from rpyc.core.service import SlaveService
import sys

print(f'[rpyc-svc] Python {sys.version}', flush=True)
print('[rpyc-svc] Listening on 0.0.0.0:${RPYC_PORT}', flush=True)
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
echo "[start-rpyc] s6 service created."
exit 0
