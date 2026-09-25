# Website deployment

This website is published from the **website** branch, with the remote set to
`https://github.com/ember-center-berkeley/VICAR.git`.

GitHub Pages serves the root of this branch at
**https://ember-center-berkeley.github.io/VICAR/**. Changes pushed to `website`
are deployed automatically.

## 1. Authenticate on a new machine

Use an authenticated Git client with write access to `ember-center-berkeley/VICAR`. For example, install [GitHub CLI](https://cli.github.com/) if needed, then run:

```sh
gh auth login
gh auth setup-git
git clone --branch website https://github.com/ember-center-berkeley/VICAR.git
cd VICAR
```

Select GitHub.com and HTTPS in the login prompts. Complete browser authentication with the account that can write to the organization repository.

Alternatively, sign into [GitHub Desktop](https://desktop.github.com/), clone this repository, and select the `website` branch.

There is no need to share your password or token in chat.

## 2. Pages configuration

These settings are already enabled. To check or restore them:

Open [the repository's Pages settings](https://github.com/ember-center-berkeley/VICAR/settings/pages) and select:

- **Source:** Deploy from a branch
- **Branch:** website
- **Folder:** / (root)

Click **Save** if you changed the settings. GitHub will create its standard Pages deployment. The website URL is:

**https://ember-center-berkeley.github.io/VICAR/**

If you see 404, check the Pages settings and deployment status in Actions. Wait until deployment succeeds before testing the public URL.

## 3. Update later

Edit `assets/content.js` for links, videos, authors, and recording paths, then:

```sh
git add assets/content.js assets/videos/ assets/images/ assets/recordings/
git commit -m "Update project media"
git push
```

GitHub Pages republishes automatically from the branch. The bundled Viser viewer runs entirely in the browser; it does not need a Python server in production.
