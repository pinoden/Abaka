# Playing Abaka online (2 to 5 players)

Each player uses their own browser. Every throw, roll, reroll and move shows up
on the other players' screens within about a second. No accounts, keys or
database are needed.

## How to play

1. The **creator** opens the app, picks the number of **Players** (2-5) in the
   **Online** card, enters a name and clicks **Create game**.
2. The app shows an invite link and a 5-character game code. Send the link to
   your friends.
3. Each friend opens the link, enters a name and clicks **Join game**.
   The game starts by itself once everyone has joined. In a game for 3-5
   players, the creator can also press **Start now** once at least one friend
   has joined.
4. Before the first round, each player throws all five dice on their own
   screen. The lowest total goes first; players who tie throw again. Play then
   goes round in the order the players joined.

Without the link, a friend can open the app, type the game code under
**Game code** in the **Online** card, click **Open game** and join from there.

When a game ends, anyone can click **Play again**. The next game opens with a
new starting throw.

## If you refresh the page or switch devices

Open the invite link again, or type the game code on the home page. The game
is still there. Tap your name under "Rejoin as" and you are back in your seat.
The tab you used before stops controlling the game.

## Where the app has to run

All players must use the **same running copy of the app**, because the game
lives on that server.

| Setup | How | Who can join |
|---|---|---|
| Hosted | Deploy to Streamlit Community Cloud (see `DEPLOYMENT_GUIDE.md`) | Anyone with the link |
| Home network | `streamlit run abaka_ui.py` on one computer | Anyone on the same Wi-Fi, using the invite link the app shows |

Every game is saved on the server's disk after every move. It survives a page
refresh, an update of the app and a restart. Games nobody has played for 7 days
are deleted. On Streamlit Community Cloud, a reboot from the dashboard or the
app going to sleep after inactivity may start from an empty disk, and saved
games would be lost then.
