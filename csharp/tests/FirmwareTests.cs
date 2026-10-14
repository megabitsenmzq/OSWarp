using System;
using System.IO;
using System.Text;

namespace OSWarp.Tests
{
    // Pure logic in Firmware.cs: id validation, order rewrite, entry
    // classification, and bcdedit output decoding from synthetic bytes.
    static class FirmwareTests
    {
        const string G1 = "{9dea862c-5cdd-4e70-acc1-f32b344d4795}";
        const string G2 = "{a5a30fa2-3d06-4e9f-b5f4-a01df9d1fcba}";
        const string G3 = "{1a5bfe4a-d959-11db-a875-e38d55d89593}";

        public static void Run()
        {
            ValidId();
            OrderWith();
            Classify();
            DecodeOutput();
        }

        static void ValidId()
        {
            T.Check("ValidId: {bootmgr}", Firmware.ValidId("{bootmgr}"));
            T.Check("ValidId: {BOOTMGR} upper", Firmware.ValidId("{BOOTMGR}"));
            T.Check("ValidId: guid", Firmware.ValidId(G1));
            T.Check("ValidId: upper guid", Firmware.ValidId(G1.ToUpperInvariant()));
            T.Check("ValidId: null rejected", !Firmware.ValidId(null));
            T.Check("ValidId: empty rejected", !Firmware.ValidId(""));
            T.Check("ValidId: bare text rejected", !Firmware.ValidId("bootmgr"));
            T.Check("ValidId: missing braces rejected", !Firmware.ValidId("9dea862c-5cdd-4e70-acc1-f32b344d4795"));
            T.Check("ValidId: short guid rejected", !Firmware.ValidId("{9dea862c-5cdd-4e70-acc1-f32b344d479}"));
            T.Check("ValidId: non-hex rejected", !Firmware.ValidId("{9dea862c-5cdd-4e70-acc1-f32b344d479z}"));
        }

        static void OrderWith()
        {
            var order = new[] { G1, G2, G3 };
            T.Eq("OrderWith: moves to front",
                G2 + " " + G1 + " " + G3,
                string.Join(" ", Firmware.OrderWith(order, G2)));
            T.Eq("OrderWith: already first",
                G1 + " " + G2 + " " + G3,
                string.Join(" ", Firmware.OrderWith(order, G1)));
            T.Eq("OrderWith: dedupes case-insensitively",
                G3 + " " + G1,
                string.Join(" ", Firmware.OrderWith(new[] { G1, G1.ToUpperInvariant() }, G3)));
            T.Throws<InvalidDataException>("OrderWith: invalid selected",
                delegate { Firmware.OrderWith(order, "not-an-id"); });
            T.Throws<InvalidDataException>("OrderWith: empty order",
                delegate { Firmware.OrderWith(new string[0], G1); });
            T.Throws<InvalidDataException>("OrderWith: null order",
                delegate { Firmware.OrderWith(null, G1); });
            T.Throws<InvalidDataException>("OrderWith: invalid member",
                delegate { Firmware.OrderWith(new[] { G1, "junk" }, G1); });
        }

        static void Classify()
        {
            T.Eq("Hint: windows dir", "Windows", Firmware.Hint("", "\\EFI\\Microsoft\\Boot\\bootmgfw.efi"));
            T.Eq("Hint: windows dir upper", "Windows", Firmware.Hint("", "\\EFI\\MICROSOFT\\BOOT\\BOOTMGFW.EFI"));
            T.Eq("Hint: windows forward slashes", "Windows", Firmware.Hint("", "/EFI/Microsoft/Boot/bootmgfw.efi"));
            T.Eq("Hint: windows loader name", "Windows", Firmware.Hint("", "\\EFI\\some\\bootmgfw.efi"));
            T.Eq("Hint: linux shim", "Linux", Firmware.Hint("", "\\EFI\\fedora\\shimx64.efi"));
            T.Eq("Hint: linux shim arm64", "Linux", Firmware.Hint("", "\\EFI\\fedora\\shimaa64.efi"));
            T.Eq("Hint: linux grub", "Linux", Firmware.Hint("", "\\EFI\\ubuntu\\grubx64.efi"));
            T.Eq("Hint: linux systemd-boot", "Linux", Firmware.Hint("", "\\EFI\\systemd\\systemd-bootx64.efi"));
            T.Eq("Hint: fallback loader unknown", "", Firmware.Hint("", "\\EFI\\BOOT\\BOOTX64.EFI"));
            T.Eq("Hint: path wins over title", "Windows", Firmware.Hint("My Linux", "\\EFI\\Microsoft\\Boot\\bootmgfw.efi"));
            T.Eq("Hint: title fallback", "Linux", Firmware.Hint("shimx64.efi rescue", ""));
            T.Eq("Hint: nothing known", "", Firmware.Hint("EFI Network", ""));
            T.Eq("Hint: empty", "", Firmware.Hint("", ""));
        }

        static void DecodeOutput()
        {
            T.Eq("DecodeOutput: null", "", Firmware.DecodeOutput(null));
            T.Eq("DecodeOutput: empty", "", Firmware.DecodeOutput(new byte[0]));

            const string text = "The boot order was updated.";
            byte[] body = Encoding.Unicode.GetBytes(text);
            var withBom = new byte[body.Length + 2];
            withBom[0] = 0xFF;
            withBom[1] = 0xFE;
            Array.Copy(body, 0, withBom, 2, body.Length);
            T.Eq("DecodeOutput: utf16le with bom", text, Firmware.DecodeOutput(withBom));

            byte[] noBom = Encoding.Unicode.GetBytes("order1234");
            T.Eq("DecodeOutput: utf16le without bom", "order1234", Firmware.DecodeOutput(noBom));

            byte[] ascii = Encoding.ASCII.GetBytes(text);
            T.Eq("DecodeOutput: ascii", text, Firmware.DecodeOutput(ascii));

            // A dump from another locale replays anywhere once its code page
            // is passed in. These bytes are GBK (code page 936).
            byte[] gbk = new byte[] { 0xB2, 0xE2, 0xCA, 0xD4 };
            T.Eq("DecodeOutput: ansi dump with explicit code page",
                "\u6D4B\u8BD5", Firmware.DecodeOutput(gbk, Encoding.GetEncoding(936)));
        }
    }
}
