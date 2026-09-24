# Publish this local checkout

This website is prepared on the local **website** branch, with the remote set to
`https://github.com/ember-center-berkeley/VICAR.git`.

The connected GitHub integration returned **403: Resource not accessible by integration** when attempting to create the first file. Nothing was uploaded through that connection. The repository is empty as of this handoff. The GitHub connection also does not expose a Pages-settings action.

## 1. Sign in locally and push

Use an authenticated Git client with write access to `ember-center-berkeley/VICAR`. For example, install [GitHub CLI](https://cli.github.com/) if needed, then run:

```sh
gh auth login
gh auth setup-git
cd /Users/dkalaria/Downloads/VICAR_ICRA_submission/website
git push -u origin website
```

Select GitHub.com and HTTPS in the login prompts. Complete browser authentication with the account that can write to the organization repository.

Alternatively, sign into [GitHub Desktop](https://desktop.github.com/), add this existing local repository, and publish/push the `website` branch to its configured remote.

There is no need to share your password or token in chat.

## 2. Enable Pages

Open [the repository's Pages settings](https://github.com/ember-center-berkeley/VICAR/settings/pages) and select:

- **Source:** Deploy from a branch
- **Branch:** website
- **Folder:** / (root)

Click **Save**. GitHub will create its standard Pages deployment. When it succeeds, the website will be at:

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
