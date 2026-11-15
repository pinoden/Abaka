# How to deploy Abaka

Hosting the app on Streamlit Community Cloud (free) gives you one public
address that both players can open, which is all online play needs.

## 1. Put the code on GitHub

The app lives at https://github.com/pinoden/Abaka. Streamlit deploys straight
from a branch of that repository, so make sure the branch you want to deploy
is pushed.

The repository must contain, at the top level:

```
abaka_ui.py        main entry point
requirements.txt   streamlit and Pillow
abaka/             game logic and online rooms
ui_components/     UI
```

## 2. Deploy

1. Go to https://share.streamlit.io and sign in with your GitHub account.
2. Click **Create app**, then choose to deploy from GitHub.
3. Repository: `pinoden/Abaka`. Branch: the branch to deploy (usually `main`).
   Main file path: `abaka_ui.py`.
4. Click **Deploy**. After a minute or so you get an address such as
   `https://your-app-name.streamlit.app`.

## 3. Play

Open the address, choose **Online (2 players)**, create a game and send your
friend the invite link the app shows. See `README_MULTIPLAYER.md`.

## Things to know

- Games are kept in the app's memory. If the app restarts, goes to sleep
  after inactivity, or is redeployed, games in progress are lost.
- The app must run as a single process (Streamlit Community Cloud does this).
  If you host it elsewhere behind several workers, players may land on
  different workers and not find each other's games.

## Running on your home network instead

```bash
pip install -r requirements.txt
streamlit run abaka_ui.py
```

`.streamlit/config.toml` already makes the app reachable from other devices
on the same Wi-Fi. Create an online game and share the invite link shown.
