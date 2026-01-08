How to Deploy Abaka OnlineFollow these steps to host your game on the web for free using Streamlit Community Cloud.Prerequisite: GitHub AccountYou need a GitHub account to host your code. If you don't have one, sign up at github.com.Step 1: Prepare your FilesEnsure you have the requirements.txt file in this folder (I just created it for you).Ensure your folder structure looks like this:Abaka/
├── abaka_ui.py       (Main entry point)
├── requirements.txt  (Dependencies)
├── abaka/            (Game logic folder)
└── ui_components/    (UI folder)
Step 2: Upload to GitHubYou need to turn this folder into a GitHub repository.Option A: Using Desktop (Easiest)Download GitHub Desktop.Open it and go to File > Add Local Repository.Select your Abaka folder.Click Create a Repository (if prompted).Click Publish repository to push it to GitHub. Make sure to uncheck "Keep this code private" if you want it to be easily accessible (or keep it private, Streamlit Cloud supports both).Option B: Using Command LineInside your Abaka folder, run:git init
git add .
git commit -m "Initial commit"
# Create a new repo on GitHub.com, then copy the remote URL
git branch -M main
git remote add origin <YOUR_GITHUB_REPO_URL>
git push -u origin main
Step 3: Deploy to Streamlit CloudGo to share.streamlit.io and sign in with your GitHub account.Click "New app".Select "Use existing repo".Repository: Select the repository you just created (e.g., yourname/abaka).Branch: Usually main or master.Main file path: Enter abaka_ui.py (or Abaka/abaka_ui.py if you uploaded the parent folder).Click "Deploy!".Step 4: Play!Streamlit will take a minute to install the requirements and launch the app.Once live, you will get a URL (e.g., https://abaka-game.streamlit.app).To Play Online:Select Online Multiplayer (Real) in the sidebar.Enter your Firebase Credentials.Create a game.Copy the URL (which now looks like https://abaka-game.streamlit.app/?game_id=...) and send it to your friend!