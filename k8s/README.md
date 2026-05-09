# Kubernetes Deployment — media-automation

Deploys Sonarr and Radarr notifier CronJobs with Tailscale sidecar containers
for MagicDNS access to `dindjarin.tail1916d.ts.net`.

## Requirements

- Kubernetes 1.28+ (for native sidecar support via `initContainers` with `restartPolicy: Always`)
- `kubectl` configured for your cluster
- A Tailscale auth key (ephemeral + reusable + pre-approved recommended)
- Container image `ghcr.io/djpadz/media-automation:latest` pushed to registry

## Pre-deployment Steps

1. **Generate a Tailscale auth key:**
   - Go to https://login.tailscale.com/admin/settings/keys
   - Create a new auth key with: Reusable ✓, Ephemeral ✓, Pre-approved ✓
   - Copy the key

2. **Update secrets in `02-tailscale-secrets.yaml`:**
   - Replace `YOUR_TAILSCALE_AUTH_KEY` with your Tailscale auth key

3. **Update secrets in `03-op-service-account-secret.yaml`:**
   - Replace `YOUR_OP_SERVICE_ACCOUNT_TOKEN` with your 1Password service account token

## Deploy

Apply in order:

```bash
kubectl apply -f k8s/00-namespace.yaml
kubectl apply -f k8s/01-tailscale-rbac.yaml
kubectl apply -f k8s/02-tailscale-secrets.yaml
kubectl apply -f k8s/03-op-service-account-secret.yaml
kubectl apply -f k8s/04-state-pvc.yaml
kubectl apply -f k8s/05-cronjob-sonarr-notifier.yaml
kubectl apply -f k8s/06-cronjob-radarr-notifier.yaml
```

Or all at once:

```bash
kubectl apply -f k8s/
```

## How It Works

Each CronJob pod has two containers sharing a network namespace:

1. **Tailscale sidecar** (native sidecar via `initContainers` + `restartPolicy: Always`):
   - Starts first, establishes Tailscale connection
   - Runs in kernel mode with `NET_ADMIN` capability
   - Enables MagicDNS (`TS_ACCEPT_DNS=true`) so all containers in the pod can resolve `*.ts.net` hostnames
   - Readiness probe ensures Tailscale is connected before the main container starts
   - Automatically terminated when the main container exits (native sidecar behavior)

2. **Notifier container** (main):
   - Runs the Python script (`notify_sonarr.py` or `notify_radarr.py`)
   - Connects to Sonarr/Radarr via Tailscale MagicDNS hostname
   - Exits when done; pod completes normally

## Architecture Notes

- **Separate state secrets** per CronJob (`tailscale-state-sonarr`, `tailscale-state-radarr`) to avoid Tailscale identity conflicts
- **Ephemeral nodes** — each pod registers as an ephemeral Tailscale node that auto-removes when the pod exits
- **Shared PVC** for notifier state files (last processed history IDs)
- **activeDeadlineSeconds: 300** — pods are killed after 5 minutes to prevent stuck jobs

## Verify

```bash
# Trigger a manual run
kubectl create job --from=cronjob/sonarr-notifier sonarr-test -n media-automation

# Watch logs
kubectl logs -n media-automation job/sonarr-test -c tailscale -f
kubectl logs -n media-automation job/sonarr-test -c sonarr-notifier -f

# Check Tailscale connected
kubectl logs -n media-automation job/sonarr-test -c tailscale | grep "Tailscale is running"

# Clean up test job
kubectl delete job sonarr-test -n media-automation
```

## Troubleshooting

- **Tailscale not connecting:** Check auth key is valid and not expired
- **DNS not resolving:** Ensure `TS_ACCEPT_DNS=true` is set; check that MagicDNS is enabled in your tailnet
- **Permission denied on tun:** Ensure `NET_ADMIN` capability is allowed by your cluster's PodSecurityPolicy/Standards
- **State secret errors:** Verify RBAC allows the ServiceAccount to create/update the state secrets

## Kubernetes < 1.28

If your cluster doesn't support native sidecars, you'll need a different approach:
the Tailscale container must detect when the main container exits and terminate itself.
See `k8s/README-legacy-sidecar.md` (not included) for a wrapper script approach.
