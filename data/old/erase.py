import pathlib
import sys

def radera_txt_filer(rotmapp: str) -> None:
    """
    Tar bort alla .txt-filer i rotmappen och alla dess undermappar.

    :param rotmapp: Fullständig sökväg till rotmappen.
    """
    path = pathlib.Path(rotmapp)

    if not path.is_dir():
        print(f"Sökvägen finns inte eller är ingen mapp: {rotmapp}")
        sys.exit(1)

    # Hitta alla .txt-filer rekursivt
    txt_filer = list(path.rglob("*.txt"))
    if not txt_filer:
        print("Inga .txt-filer hittades.")
        return

    for fil in txt_filer:
        try:
            fil.unlink()
            print(f"Raderade: {fil}")
        except Exception as e:
            print(f"Kunde inte radera {fil}: {e}")

if __name__ == "__main__":
    ROTMAPP = r"C:\Users\Propietario\Desktop\data\tree"   # justera om nödvändigt
    radera_txt_filer(ROTMAPP)
