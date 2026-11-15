# Playing Abaka online (2 players)

Each player uses their own browser. Every roll, reroll and score shows up on
the other player's screen within about a second. No accounts, keys or
database are needed.

## How to play

1. **Player 1** opens the app, enters a name in the **Online** card and clicks
   **Create game**.
2. The app shows an invite link (and a 5-letter game code). Send the link to
   your friend.
3. **Player 2** opens the link, enters a name and clicks **Join game**.
   The game starts right away. Player 1 rolls first.

Without the link, Player 2 can open the app, type the game code under
**or join with a code** in the **Online** card and click **Join game**.

When a game ends, either player can click **Play again**; the other player
starts the next game.

## If you refresh the page or switch devices

Open the invite link again. The game is still there. Tap your name under
"Rejoin as" and you are back in your seat. The tab you used before stops
controlling the game.

## Where the app has to run

Both players must use the **same running copy of the app**, because the game
is kept in that server's memory.

| Setup | How | Who can join |
|---|---|---|
| Hosted | Deploy to Streamlit Community Cloud (see `DEPLOYMENT_GUIDE.md`) | Anyone with the link |
| Home network | `streamlit run abaka_ui.py` on one computer | Anyone on the same Wi-Fi, using the invite link the app shows |

Games are lost if the app restarts (for example, when a hosted app goes to
sleep after inactivity or is redeployed). Rooms that nobody touches for 12
hours are removed.
