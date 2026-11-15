# Playing Abaka online (2 to 5 players)

Each player uses their own browser. Every roll, reroll and score shows up on
the other players' screens within about a second. No accounts, keys or
database are needed.

## How to play

1. The **creator** opens the app, picks the number of **Players** (2-5) in the
   **Online** card, enters a name and clicks **Create game**.
2. The app shows an invite link (and a 5-letter game code). Send the link to
   your friends.
3. Each friend opens the link, enters a name and clicks **Join game**.
   The game starts by itself once everyone has joined, and the creator rolls
   first. In a game for 3-5 players, the creator can also press
   **Start now** once at least one friend has joined.

Without the link, a friend can open the app, type the game code under
**or join with a code** in the **Online** card and click **Join game**.

Players take turns in the order they joined. When a game ends, anyone can
click **Play again**; the next player in order starts the next game.

## If you refresh the page or switch devices

Open the invite link again. The game is still there. Tap your name under
"Rejoin as" and you are back in your seat. The tab you used before stops
controlling the game.

## Where the app has to run

All players must use the **same running copy of the app**, because the game
is kept in that server's memory.

| Setup | How | Who can join |
|---|---|---|
| Hosted | Deploy to Streamlit Community Cloud (see `DEPLOYMENT_GUIDE.md`) | Anyone with the link |
| Home network | `streamlit run abaka_ui.py` on one computer | Anyone on the same Wi-Fi, using the invite link the app shows |

Games are lost if the app restarts (for example, when a hosted app goes to
sleep after inactivity or is redeployed). Rooms that nobody touches for 12
hours are removed.
