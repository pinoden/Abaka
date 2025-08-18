# abaka/school.py
from __future__ import annotations
from .models import Category

def record_school(engine, category: Category, slot_index: int) -> None:
    """
    Школа (баланс):
      - k = число кубиков нужной номиналы; joker(1) добавляет +1 для любого denom != 1.
      - k == 3 → клетка школы ставится 'X' (ровно три, баланс не меняется).
      - k > 3 → добавить (k-3)*denom к балансу (записать новое значение).
      - k < 3 → платим недостачу:
          * если k >= 1 → стоимость (3-k)*denom;
          * если k == 0 → стоимость 2*denom.
        Обычная игра: (k==0 запрещён) и баланс должен хватать.
        Эндгейм: если вся нижняя часть заполнена (p.non_school_complete()),
                 разрешаем уходить в минус при любом k<3.
      - ВАЖНО: в школе НИКОГДА не действует удвоение первого броска.
      - Любой «минус» в школе мгновенно перечёркивает бонус строки школы у игрока.
    """
    p = engine.players[engine.current]
    denom = int(category.name.split('_')[1])

    # считаем k
    k = sum(1 for d in engine.dice if d.value == denom)
    if denom != 1 and any(d.is_joker and d.value == 1 for d in engine.dice):
        k += 1

    # ровно три → крестик
    if k == 3:
        p.cross(category, slot_index)
        return

    def move_balance(new_value: int) -> None:
        # гасим прошлую ячейку баланса (если была), пишем новую
        if p.school_balance_loc is not None:
            pc, ps = p.school_balance_loc
            p.table[pc][ps] = 'X'
        val = new_value          # <-- БЕЗ удвоения в школе
        p.record(category, slot_index, val)
        p.school_balance = val
        p.school_balance_loc = (category, slot_index)

    # излишек
    if k > 3:
        delta = (k - 3) * denom
        move_balance(p.school_balance + delta)
        return

    # недостача (k < 3)
    required = (3 - k) * denom if k >= 1 else 2 * denom

    # запрет k==0 до эндгейма
    if k == 0 and not p.non_school_complete():
        raise ValueError("Cannot write this school row: need at least one die of that denomination")

    # хватает баланса — обычный минус
    if p.school_balance >= required:
        move_balance(p.school_balance - required)
        engine.school_minus_used[(engine.current, category)] = True
        if p.table[category][3] is None:
            p.table[category][3] = 'X'
        return

    # эндгейм — разрешаем уходить в минус
    if p.non_school_complete():
        move_balance(p.school_balance - required)  # может стать отрицательным
        engine.school_minus_used[(engine.current, category)] = True
        if p.table[category][3] is None:
            p.table[category][3] = 'X'
        return

    # иначе недостаточно баланса
    raise ValueError(f"Not enough school balance to write this row (need {required}, have {p.school_balance})")
