# The American Over

Official website for The American Over, a podcast about cricket in the United States.

The site is a static build intended for GitHub Pages.

## Episode updates

The `Sync RSS and deploy` GitHub Action checks the Zencastr RSS feed every hour. When an episode changes, it rebuilds the latest-episode card and episode list, commits the updated `index.html`, and deploys the site to GitHub Pages.

To check immediately after publishing an episode, open the repository's **Actions** tab, choose **Sync RSS and deploy**, and select **Run workflow**.
