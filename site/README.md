# Gardens — Landing Page

This folder contains the static landing page for the Gardens project.

## URL

Live at: https://gardens.adaequa.com

## Deployment

The page is served by the `hosting-nginx` container on the VPS. To update it:

1. Edit `site/index.html` in this repository.
2. Copy it to the VPS webroot:
   ```bash
   cp site/index.html /home/ubuntu/.openclaw/workspace/docker-hosting/web/gardens/index.html
   ```
3. Restart Nginx if needed:
   ```bash
   docker restart hosting-nginx
   ```

## Content

The landing page is intentionally simple: a single HTML file with inline CSS. It presents the project, proposes three entry points based on the visitor's situation, and invites them to stay informed.
