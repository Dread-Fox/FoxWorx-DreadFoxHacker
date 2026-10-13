# Upload FoxWorx DreadFoxHacker to GitHub

The public repository is `https://github.com/Dread-Fox/FoxWorx-DreadFoxHacker`.

## Before publishing

1. Confirm FoxWorx LLC owns or has permission to relicense the original code. The bundled third-party assets keep their own notices.
2. Review all files for secrets, private endpoints, credentials, customer data, and private assessment output.
3. Confirm you understand that anyone can view and technically clone a **public** repository even though the proprietary LICENSE prohibits unauthorized use.

## Upload from your Kali machine

Authenticate your own GitHub account using `gh auth login` or Git Credential Manager. Never paste access tokens into FOXWORX or chat.

```bash
git clone https://github.com/Dread-Fox/FoxWorx-DreadFoxHacker.git
# Extract FoxWorx-DreadFoxHacker-v3.3.3.zip in the same parent folder.
# It creates a folder named FoxWorx-DreadFoxHacker-v3.3.3.
cp -a FoxWorx-DreadFoxHacker-v3.3.3/. FoxWorx-DreadFoxHacker/
cd FoxWorx-DreadFoxHacker
git status --short
# Double-check that no runtime secrets or private assessment files are staged.
git add -A
git diff --cached --stat
git commit -m "Release FOXWORX Kali Workbench v3.3.3 (proprietary)"
git push origin main
```

If you place the ZIP elsewhere, adjust the paths. If GitHub prompts for credentials, use the browser credential flow or GitHub CLI; account passwords aren't accepted as Git HTTPS passwords.

## Confirm publication

Check these URLs:
- https://github.com/Dread-Fox/FoxWorx-DreadFoxHacker
- https://github.com/Dread-Fox/FoxWorx-DreadFoxHacker/blob/main/LICENSE
- https://github.com/Dread-Fox/FoxWorx-DreadFoxHacker/blob/main/docs/INSTALL.md
- https://github.com/Dread-Fox/FoxWorx-DreadFoxHacker/blob/main/docs/OPERATOR-GUIDE.md

To install, see `docs/INSTALL.md`. Use the administrator policies in `policy/` only after review; they control Rabbit Hole execution.

**v3.3:** Do not commit any bot token, client evidence or team channel history. Discord integration requires private host configuration; see docs/DISCORD-TEAM.md.
