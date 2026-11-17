"""
Interface text in English and Russian.

Texts are written in English in the code and wrapped in t("..."), which returns
the Russian version when the page is in Russian. tests/test_i18n.py checks that
every t("...") text in the code has a Russian version here.

The language is set once at the start of every script run (abaka_ui.main), per
thread, because Streamlit runs each browser session's script in its own thread.
No Streamlit here, so moves.py and the tests can use it.
"""

import re
import threading

LANGUAGES = {"en": "English", "ru": "Русский"}
_local = threading.local()


def set_language(code: str) -> None:
    _local.lang = code if code in LANGUAGES else "en"


def get_language() -> str:
    return getattr(_local, "lang", "en")


def t(text: str, **values) -> str:
    """`text` (an English template) in the current language, with {values} filled in."""
    if get_language() == "ru":
        text = RU.get(text, text)
    return text.format(**values) if values else text


def _ru_plural(n: int, one: str, few: str, many: str) -> str:
    n = abs(n)
    if n % 10 == 1 and n % 100 != 11:
        return one
    if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14:
        return few
    return many


def rerolls_left(n: int) -> str:
    if get_language() == "ru":
        return f"{n} {_ru_plural(n, 'переброс', 'переброса', 'перебросов')}"
    return "1 reroll" if n == 1 else f"{n} rerolls"


def reroll_dice(n: int) -> str:
    """The Reroll button when `n` dice are picked."""
    if get_language() == "ru":
        return f"Перебросить {n} {_ru_plural(n, 'кубик', 'кубика', 'кубиков')}"
    return f"Reroll {n} {'die' if n == 1 else 'dice'}"


def players_count(n: int) -> str:
    """'3 players' (Start now with ...)."""
    if get_language() == "ru":
        return f"{n} {_ru_plural(n, 'игрок', 'игрока', 'игроков')}"
    return f"{n} players"


_MD_SPECIAL = re.compile(r"([\\`*_{}\[\]()#+\-.!|<>~$:])")
_LINK_BREAK = re.compile(r"(\\[.:]|@)")
_ZERO_WIDTH_SPACE = "​"


def md(text: str) -> str:
    """
    Text a player typed (a name), made safe for places Streamlit renders as Markdown:
    captions, toasts and button labels. Links, images, formatting and bare URLs stay
    plain text. HTML places use html.escape instead.

    Backslash escapes stop Markdown syntax, but captions and toasts still turn bare
    addresses (http://..., www...., name@host) into links, so a zero-width space
    after every ":", "." and "@" breaks them up. It is invisible.
    """
    escaped = _MD_SPECIAL.sub(r"\\\1", text)
    return _LINK_BREAK.sub(lambda m: m.group(1) + _ZERO_WIDTH_SPACE, escaped)


def and_join(names) -> str:
    """'Ann and Bob', 'Ann, Bob and Cy'."""
    names = list(names)
    if len(names) < 2:
        return "".join(names)
    return f"{', '.join(names[:-1])} {t('and')} {names[-1]}"


# Messages from the engine and the rooms (RoomError / ValueError texts shown to players).
_ERRORS_RU = {
    "This game is already full.": "Эта игра уже заполнена.",
    "The app was just updated. Please try again.": "Приложение только что обновилось. Попробуйте ещё раз.",
    "Only the player who created the game can start it.": "Начать игру может только тот, кто её создал.",
    "The game has already started.": "Игра уже началась.",
    "Wait until at least one more player has joined.": "Дождитесь, пока подключится хотя бы ещё один игрок.",
    "That seat does not exist.": "Такого места нет.",
    "Game not found. Check the code, or ask for a new invite.":
        "Игра не найдена. Проверьте код или попросите новое приглашение.",
    "You are not seated in this game.": "Вы не участвуете в этой игре.",
    "Waiting for the second player to join.": "Ждём второго игрока.",
    "The game is over.": "Игра окончена.",
    "It is not your turn.": "Сейчас не ваш ход.",
    "Roll the dice first.": "Сначала бросьте кубики.",
    "No rerolls left.": "Перебросов не осталось.",
    "No rerolls left": "Перебросов не осталось.",
    "You have already rolled this turn.": "Вы уже бросали кубики в этом ходу.",
    "The first player has already been decided.": "Первый игрок уже определён.",
    "This is an online game: join it or rejoin as one of its players.":
        "Это онлайн-игра: присоединитесь к ней или вернитесь как один из игроков.",
    "A game is for 2 to 5 players.": "В игре от 2 до 5 игроков.",
    "The current game is not finished yet.": "Текущая игра ещё не закончена.",
    "Throw for the first turn first: the lowest throw starts.":
        "Сначала бросок за первый ход: начинает тот, у кого сумма меньше.",
    "Cannot write this school row: need at least one die of that denomination":
        "Эту строку школы не записать: нужен хотя бы один кубик с этим числом.",
    "Slot already filled": "Эта клетка уже заполнена.",
    "Row already complete": "Эта строка уже заполнена.",
}
_ERROR_PATTERNS_RU = [
    (re.compile(r"Not enough school balance to write this row \(need (\d+), have (-?\d+)\)"),
     "Не хватает баланса школы для этой строки (нужно {0}, есть {1})."),
]


def error(message: str) -> str:
    """A message from the engine or the rooms, in the current language."""
    if get_language() != "ru":
        return message
    if message in _ERRORS_RU:
        return _ERRORS_RU[message]
    for pattern, template in _ERROR_PATTERNS_RU:
        match = pattern.fullmatch(message)
        if match:
            return template.format(*match.groups())
    return message


RU = {
    # ----- general -----
    "and": "и",
    "You": "Вы",
    "Name": "Имя",
    "Player {i}": "Игрок {i}",
    "Language": "Язык",
    # ----- home -----
    "The dice game of combinations. Play with friends on one screen or online.":
        "Игра в кости на комбинации. Играйте с друзьями на одном экране или онлайн.",
    "Continue a game": "Продолжить игру",
    "Your games are saved after every move.": "Игры сохраняются после каждого хода.",
    "Same device": "Одно устройство",
    "Take turns on this screen.": "Ходите по очереди на этом экране.",
    "Players": "Игроки",
    "Start game": "Начать игру",
    "Online": "Онлайн",
    "Each player on their own device. Invite friends with a link.":
        "Каждый игрок на своём устройстве. Пригласите друзей по ссылке.",
    "Your name": "Ваше имя",
    "Create game": "Создать игру",
    "or open a game by its code": "или откройте игру по коду",
    "Game code": "Код игры",
    "e.g. Q47CH": "например, Q47CH",
    "Join a friend's game, or continue a saved game.": "Присоединиться к игре друга или продолжить сохранённую.",
    "Open game": "Открыть игру",
    "No game with that code. Check it and try again.": "Игры с таким кодом нет. Проверьте код и попробуйте ещё раз.",
    "How to play": "Как играть",
    "Same device · {code}": "Одно устройство · {code}",
    "Online · {code}": "Онлайн · {code}",
    "{code} · {kind} · {names}": "{code} · {kind} · {names}",
    "Game {code} is saved. To continue it, open it from this page or enter the code {code}.":
        "Игра {code} сохранена. Чтобы продолжить, откройте её на этой странице или введите код {code}.",
    "This game was opened in another tab or device, so this tab no longer controls it.":
        "Эта игра открыта в другой вкладке или на другом устройстве, поэтому эта вкладка больше ею не управляет.",
    "That game is no longer available.": "Эта игра больше недоступна.",
    # ----- waiting room -----
    "Invite a friend": "Пригласите друга",
    "Invite your friends": "Пригласите друзей",
    "Send them this link. The game starts as soon as they join.":
        "Отправьте эту ссылку. Игра начнётся, как только друг подключится.",
    "Send them this link. The game starts when all {n} players have joined.":
        "Отправьте эту ссылку. Игра начнётся, когда соберутся все игроки ({n}).",
    "You're in!": "Вы в игре!",
    "The game starts when all {capacity} players have joined, or when {host} starts it. "
    "You can invite people with this link too.":
        "Игра начнётся, когда соберутся все игроки ({capacity}) или когда {host} её запустит. "
        "Приглашать можно и по этой ссылке.",
    "This link works for devices on the same Wi-Fi. To play over the internet, deploy the app "
    "(see DEPLOYMENT_GUIDE.md).":
        "Эта ссылка работает для устройств в той же сети Wi-Fi. Чтобы играть через интернет, "
        "разверните приложение (см. DEPLOYMENT_GUIDE.md).",
    "or share the game code": "или сообщите код игры",
    "Waiting…": "Ждём…",
    "Waiting for your friend to join…": "Ждём, пока друг подключится…",
    "{joined} of {capacity} players are here. Waiting for {missing} more…":
        "Собралось {joined} из {capacity}. Ждём ещё {missing}…",
    "Start now with {players}": "Начать сейчас: {players}",
    "Cancel": "Отменить",
    "Leave": "Выйти",
    "Leave game": "Выйти из игры",
    "{names} left.": "{names} больше нет в игре.",
    " You're the host now.": " Теперь ведущий — вы.",
    "{name} joined.": "{name} в игре.",
    "Everyone's here.": "Все в сборе.",
    "Your turn!": "Ваш ход!",
    "Your throw!": "Ваш бросок!",
    # ----- invite page -----
    "Game not found": "Игра не найдена",
    "Game {code} has ended, or it is no longer kept. You can start a new one.":
        "Игра {code} закончилась или больше не хранится. Можно начать новую.",
    "Go to start": "На главную",
    "{host} invited you to play": "{host} приглашает вас в игру",
    "Enter your name to join. The game starts right away.": "Введите имя, чтобы присоединиться. Игра начнётся сразу.",
    "A game for {n} players; {k} joined so far: {names}. Enter your name to join.":
        "Игра для {n} игроков; уже в игре ({k}): {names}. Введите имя, чтобы присоединиться.",
    "Join game": "Присоединиться",
    "Already joined and lost the page? Rejoin as:": "Уже были в игре и потеряли страницу? Вернуться как:",
    " vs ": " против ",
    "This game is full and already playing.": "Игра уже идёт, свободных мест нет.",
    "Are you one of the players? Rejoin as:": "Вы один из игроков? Вернуться как:",
    "Start your own game instead": "Начать свою игру",
    # ----- game: top bar, turn -----
    "Menu": "Меню",
    "Your turn": "Ваш ход",
    "{name}’s turn": "Ходит {name}",
    "Roll {n} of 3": "Бросок {n} из 3",
    "First roll: combinations score double": "Первый бросок: комбинации считаются вдвойне",
    "Roll the dice to start the turn.": "Бросьте кубики, чтобы начать ход.",
    "Waiting for {name} to roll…": "Ждём, пока {name} бросит кубики…",
    "Roll dice": "Бросить кубики",
    "{name} is choosing a move. You will see it here as it happens.":
        "{name} выбирает ход. Вы увидите его здесь сразу же.",
    # ----- starting throw -----
    "Who goes first?": "Кто ходит первым?",
    "Everyone throws all five dice. The lowest total goes first.":
        "Все бросают пять кубиков. Первым ходит тот, у кого сумма меньше.",
    "A tie for the lowest total: {names} throw again.": "Ничья по наименьшей сумме: {names} бросают ещё раз.",
    "throws next": "бросает",
    "waiting": "ждёт",
    "Waiting for {name} to throw…": "Ждём, пока {name} бросит кубики…",
    "Throw the dice": "Бросить кубики",
    "Throw for {name}": "Бросок: {name}",
    "You threw the lowest ({total}) and go first.": "Первый ход ваш: наименьшая сумма ({total}).",
    "{name} threw the lowest ({total}) and goes first.": "Первый ход: {name} (наименьшая сумма — {total}).",
    # ----- results -----
    "It’s a draw!": "Ничья!",
    "You win!": "Вы победили!",
    "{name} wins!": "Победа: {name}!",
    "Play again": "Сыграть ещё",
    # ----- dice -----
    "joker": "джокер",
    "wild joker": "любой",
    "{value} (joker)": "{value} (джокер)",
    "Rolls used": "Использовано бросков",
    "No rerolls left. Choose where to write this roll.": "Перебросов не осталось. Выберите, куда записать бросок.",
    "Tap the dice you want to roll again ({left} left), or choose a move below.":
        "Нажмите на кубики, которые хотите перебросить (осталось {left}), или выберите ход ниже.",
    "Reroll picked": "Перебросить выбранные",
    "Reroll all": "Перебросить все",
    # ----- move picker -----
    "Write this roll": "Запишите бросок",
    "Score": "Записать",
    "Cross out": "Зачеркнуть",
    "Nothing can be scored with these dice. Reroll, or switch to **Cross out**.":
        "С этими кубиками ничего не записать. Перебросьте или выберите **Зачеркнуть**.",
    "There is nothing left to cross out.": "Зачёркивать больше нечего.",
    "Choose a row above": "Выберите строку выше",
    "Choose a row to cross out": "Выберите строку, чтобы зачеркнуть",
    # ----- rows and moves -----
    "Pair": "Пара",
    "Two pairs": "Две пары",
    "Three of a kind": "Тройка",
    "Small straight": "Малый стрит",
    "Large straight": "Большой стрит",
    "Full house": "Фулл-хаус",
    "Four of a kind": "Каре",
    "Abaka": "Абака",
    "Sum": "Сумма",
    "School {n}": "Школа {n}",
    "Two dice of the same number. Scores the pair.": "Два кубика с одним числом. Очки — сумма пары.",
    "Two different pairs. Scores both pairs.": "Две разные пары. Очки — сумма обеих пар.",
    "Three of the same number. Scores the three.": "Три кубика с одним числом. Очки — их сумма.",
    "Exactly 1-2-3-4-5. Scores 15.": "Ровно 1-2-3-4-5. 15 очков.",
    "Exactly 2-3-4-5-6. Scores 20.": "Ровно 2-3-4-5-6. 20 очков.",
    "Three of one number and two of another. Scores all dice; 1-1-1-2-2 adds 50.":
        "Три одного числа и два другого. Очки — сумма всех кубиков; за 1-1-1-2-2 ещё 50.",
    "Four of the same number. Scores the four, plus 20.": "Четыре кубика с одним числом. Их сумма плюс 20.",
    "All five dice the same. Scores all dice, plus 50.": "Все пять кубиков одинаковые. Их сумма плюс 50.",
    "Any dice. Scores the total.": "Любые кубики. Очки — сумма.",
    "Three {n}s are par. Extra {n}s add to your school balance; fewer {n}s are paid from it, "
    "which crosses out this row's bonus.":
        "Три кубика «{n}» — норма. Каждый лишний добавляет {n} к балансу школы; каждый недостающий "
        "оплачивается из баланса, и бонус этой строки зачёркивается.",
    "{name} · exactly 3": "{name} · ровно 3",
    "{name} · {value}": "{name} · {value}",
    "Cross out {name}": "Зачеркнуть «{name}»",
    "Cross out {name} (lose the row and column bonuses)": "Зачеркнуть «{name}» (бонусы строки и столбца сгорают)",
    "Cross out {name} (lose the row bonus)": "Зачеркнуть «{name}» (бонус строки сгорает)",
    "Cross out {name} (lose the column bonus)": "Зачеркнуть «{name}» (бонус столбца сгорает)",
    "Write {name} (exactly three)": "Записать «{name}» (ровно три)",
    "Write {name} (+{n} balance)": "Записать «{name}» (+{n} к балансу)",
    "Write {name} (pay {n} from balance)": "Записать «{name}» (−{n} из баланса)",
    "Write {name} (pay {n} from balance, lose the row bonus)":
        "Записать «{name}» (−{n} из баланса, бонус строки сгорает)",
    "Score {value} in {name}": "Записать {value} в «{name}»",
    # ----- scoreboard -----
    "School": "Школа",
    "Combinations": "Комбинации",
    "Bonuses & total": "Бонусы и итог",
    "Column bonus": "Бонус столбца",
    "Total": "Итого",
    "{score} pts": "{score} очк.",
    "balance {balance}": "баланс {balance}",
    "Row bonus": "Бонус строки",
    "Done": "Готово",
    "Crossed out": "Зачёркнуто",
    "No bonus": "Без бонуса",
    "Bonus crossed out": "Бонус зачёркнут",
    "This move crosses out the row bonus": "Этот ход зачёркивает бонус строки",
    "This move crosses out the column bonus": "Этот ход зачёркивает бонус столбца",
    "Complete a column with no crossed-out combinations": "Заполните столбец без зачёркнутых комбинаций",
    "Last move: {who} {what}": "Последний ход — {who}: {what}",
    "scored {value} in {name}": "{value} в «{name}»",
    "crossed out {name}": "зачёркнуто «{name}»",
    "wrote {name} (exactly three)": "«{name}», ровно три",
    "wrote {name} (balance now {value})": "«{name}», баланс теперь {value}",
}
