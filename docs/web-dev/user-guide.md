# User guide

The interface is in Uzbek; the English meaning of each button is given in brackets.
Screenshots are in [`docs/screenshots/`](../screenshots/).

## Roles

| Role | Can do |
|---|---|
| **Manager** (*boshqaruvchi*) | add and edit orders, start and finish stages, record material arrival, correct or remove a stage record |
| **Owner** (*egasi*) | everything a manager can, plus approve and block users, change roles and delete orders |

## Getting an account

1. On the login page press **Roʻyxatdan oʻtish** (Register).
2. Choose a login (3–30 Latin letters, digits or `_`) and a password of at least 8 characters.
3. The account stays inactive until the owner approves it. Until then, logging in shows
   *“Hisobingiz hali egasi tomonidan tasdiqlanmagan”* (your account is not approved yet).

After five wrong passwords the login form is locked for ten minutes.

## Recording an order

1. On the main page press **+ Yangi buyurtma** (New order).
2. Enter the workshop's own **order number**. Do not enter the client's name.
3. Tap the **box type**, the **quantity** (1000 / 1500 / 2000 or type another number) and,
   for colour and micro boxes, the **finishing** the client chose: none, lamination or lacquer.
4. **Xomashyo omborda bormi?** (Is the material in stock?) – Ha / Yoʻq. If not, you can fill
   in when it arrived, or leave it empty and record it later.
5. Enter **when the order was received**, and optionally the promised date.
6. Press **Saqlash** (Save). The order page opens.

## Recording production stages

The order page lists the stages of this box type in workshop order.

- **Boshlash** (Start) – the stage starts now. If it started earlier, use **Boshqa vaqt**
  (Other time) and enter the real time.
- **Tugatish** (Finish) – enter the number of finished boxes (filled in with the order
  quantity), the number of defective boxes (− / + buttons) and whether 1 or 2 people worked.
  The finish time is *now*; open **Oʻzgartirish** to enter the real time.
- Paper cutting and corrugated board cutting can run at the same time; both can be started.
- When the last stage is finished, the order becomes **Tayyor** (Completed) automatically.

Mistakes:

- **Tahrirlash** (Edit) on a finished stage changes its times or counts.
- **Oʻchirish / Bekor qilish** (Delete / Cancel) removes a stage record so it can be entered again.
  If the order was completed, it is reopened.

## Material arrival

For an order whose material was not in stock, the order page shows a yellow card.
When the material arrives, check the time and press **Xomashyo keldi** (Material arrived).

## Editing and deleting orders

- **Buyurtmani tahrirlash** (Edit order) changes the number, quantity, times or material.
  Box type and finishing are locked once a stage has been recorded, because they decide the stages.
- **Buyurtmani oʻchirish** (Delete order) – owner only – removes the order and all its stages
  after a confirmation.

## Managing users (owner)

**Foydalanuvchilar** (Users) in the top bar lists every account:

- **Tasdiqlash** (Approve) a new registration, **Bloklash** (Block) an account;
- **Egasi qilish / Boshqaruvchi qilish** – make someone owner or manager.

An owner cannot block or demote their own account, so the workshop can never be left without an owner.
