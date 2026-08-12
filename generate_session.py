import asyncio

from pyrogram import Client


async def main():
    print("=" * 55)
    print("   TELEGRAM MUSIC BOT - SESSION GENERATOR")
    print("=" * 55)
    print()
    print("Program ini akan membuat SESSION_STRING.")
    print("SESSION_STRING digunakan agar akun Telegram")
    print("bisa digunakan oleh music bot di Railway.")
    print()

    # =====================================================
    # API ID
    # =====================================================

    api_id_input = input("Masukkan API ID: ").strip()

    try:
        api_id = int(api_id_input)

    except ValueError:
        print()
        print("❌ API ID harus berupa angka.")
        return

    # =====================================================
    # API HASH
    # =====================================================

    api_hash = input(
        "Masukkan API HASH: "
    ).strip()

    if not api_hash:
        print()
        print("❌ API HASH tidak boleh kosong.")
        return

    print()
    print("Membuka koneksi Telegram...")
    print()

    # =====================================================
    # PYROGRAM CLIENT
    # =====================================================

    app = Client(
        "session_generator",
        api_id=api_id,
        api_hash=api_hash,
        in_memory=True,
    )

    try:

        await app.start()

        # =================================================
        # INFORMASI AKUN
        # =================================================

        me = await app.get_me()

        # =================================================
        # EXPORT SESSION STRING
        # =================================================

        session_string = (
            await app.export_session_string()
        )

        print()
        print("=" * 55)
        print("             LOGIN BERHASIL")
        print("=" * 55)
        print()

        print(
            f"Nama akun : {me.first_name}"
        )

        if me.username:
            print(
                f"Username  : @{me.username}"
            )

        print(
            f"Telegram ID : {me.id}"
        )

        print()
        print("=" * 55)
        print("               SESSION_STRING")
        print("=" * 55)
        print()

        print(session_string)

        print()
        print("=" * 55)
        print()
        print("⚠️ PENTING:")
        print()
        print("JANGAN kirim SESSION_STRING kepada orang lain.")
        print("JANGAN upload SESSION_STRING ke GitHub.")
        print("Simpan SESSION_STRING untuk dimasukkan ke")
        print("Railway Variables.")
        print()

    except Exception as exc:

        print()
        print("=" * 55)
        print("❌ LOGIN GAGAL")
        print("=" * 55)
        print()
        print(
            f"Error: {type(exc).__name__}: {exc}"
        )
        print()

    finally:

        try:
            await app.stop()

        except Exception:
            pass


if __name__ == "__main__":

    asyncio.run(
        main()
    )
