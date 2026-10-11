using System;
using System.Collections.Generic;

namespace OSWarp
{
    static class Boot
    {
        public static string Mode = "";
        public static bool HasOneShot;
        public static List<FirmwareEntry> Entries = new List<FirmwareEntry>();
        public static List<string> Order = new List<string>();

        public static string Load()
        {
            Entries = new List<FirmwareEntry>();
            Order = new List<string>();
            HasOneShot = false;
            try
            {
                FirmwareCatalog catalog = Firmware.Catalog();
                Entries = catalog.Entries;
                Order = catalog.Order;
                HasOneShot = catalog.HasOneShot;
                if (Entries.Count == 0)
                    return "No firmware boot entries.";
                return null;
            }
            catch (Exception ex)
            {
                string inner = ex.InnerException != null ? "\n" + ex.InnerException.GetType().Name + ": " + ex.InnerException.Message : "";
                return "Could not read firmware boot entries.\n" + ex.GetType().Name + ": " + ex.Message + inner;
            }
        }

        public static string Commit(FirmwareEntry entry)
        {
            if (Mode != "bootorder" && Mode != "bootnext")
                return "The boot setting is not valid.";
            try
            {
                Config.Save(Mode, entry.Id);
            }
            catch (Exception)
            {
                // A settings write must not block the firmware change.
            }
            return Mode == "bootnext" ? CommitNext(entry) : CommitOrder(entry);
        }

        static string CommitOrder(FirmwareEntry entry)
        {
            try
            {
                string[] next = Firmware.OrderWith(Order, entry.Id);
                Actions.RunBcdedit("/set {fwbootmgr} displayorder " + string.Join(" ", next));
            }
            catch (Exception ex)
            {
                return "Did not reboot.\n" + ex.Message;
            }
            if (HasOneShot)
            {
                try
                {
                    Actions.RunBcdedit("/deletevalue {fwbootmgr} bootsequence");
                }
                catch (Exception ex)
                {
                    return "The boot order was changed, but the next-boot setting could not be cleared.\n" + ex.Message;
                }
            }
            try
            {
                Actions.Reboot();
                return null;
            }
            catch (Exception ex)
            {
                return "The boot order was changed, but the reboot did not happen.\n" + ex.Message;
            }
        }

        static string CommitNext(FirmwareEntry entry)
        {
            try
            {
                Actions.RunBcdedit("/set {fwbootmgr} bootsequence " + entry.Id);
            }
            catch (Exception ex)
            {
                return "Did not reboot.\n" + ex.Message;
            }
            try
            {
                Actions.Reboot();
                return null;
            }
            catch (Exception ex)
            {
                return "The next boot was changed, but the reboot did not happen.\n" + ex.Message;
            }
        }

    }
}
