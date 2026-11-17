# How to deploy Abaka

Hosting the app on Streamlit Community Cloud (free) gives you one public
address that every player can open, which is all online play needs. The live
app is https://mipt-abaka.streamlit.app/.

## 1. Put the code on GitHub

The app lives at https://github.com/pinoden/Abaka. Streamlit deploys straight
from a branch of that repository (`main` for the live app).

The repository must contain, at the top level:

```
abaka_ui.py        main entry point
code_version.py    reloads the game modules after an update
requirements.txt   Streamlit, pinned to one version
.streamlit/        server settings and colour theme
abaka/             the game and its rooms
ui_components/     the interface
```

## 2. Deploy

1. Go to https://share.streamlit.io and sign in with your GitHub account.
2. Click **Create app**, then choose to deploy from GitHub.
3. Repository: `pinoden/Abaka`. Branch: `main`. Main file path: `abaka_ui.py`.
4. Under **Advanced settings**, pick Python 3.11 or newer; the pinned Streamlit
   needs it. The live app runs Python 3.13.
5. Click **Deploy**. After a minute or so you get an address such as
   `https://your-app-name.streamlit.app`.

A merge into the deployed branch updates the running app, usually within a few
minutes, and games in progress carry on. A change to `requirements.txt` makes
Streamlit install the packages again and restart the app.

## 3. Play

Open the address, create a game in the **Online** card and send your friends
the invite link the app shows. See `README_MULTIPLAYER.md`.

## Things to know

- Games are saved on the server's disk, in `~/.abaka/games` or the folder named
  by `ABAKA_SAVE_DIR`. They survive updates and restarts of the app. On
  Streamlit Community Cloud they probably do not survive a reboot from the
  dashboard or the app going to sleep after inactivity, because those start
  from an empty disk.
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
