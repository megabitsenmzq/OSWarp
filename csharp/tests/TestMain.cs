using System;

namespace OSWarp.Tests
{
    // Tiny assertion helpers shared by every test group.
    static class T
    {
        public static int Passed;
        public static int Failed;
        public static int Skipped;

        public static void Check(string name, bool ok)
        {
            if (ok)
            {
                Passed++;
                Console.WriteLine("PASS  " + name);
            }
            else
            {
                Failed++;
                Console.WriteLine("FAIL  " + name);
            }
        }

        public static void Eq(string name, object want, object got)
        {
            bool ok = Object.Equals(want, got);
            if (!ok)
                Console.WriteLine("      want: " + Show(want) + "  got: " + Show(got));
            Check(name, ok);
        }

        public static void Throws<TEx>(string name, Action body) where TEx : Exception
        {
            try
            {
                body();
                Console.WriteLine("      nothing was thrown");
                Check(name, false);
            }
            catch (TEx)
            {
                Check(name, true);
            }
            catch (Exception ex)
            {
                Console.WriteLine("      wrong exception: " + ex.GetType().Name + ": " + ex.Message);
                Check(name, false);
            }
        }

        public static void Skip(string name, string why)
        {
            Skipped++;
            Console.WriteLine("SKIP  " + name + " (" + why + ")");
        }

        static string Show(object value)
        {
            return value == null ? "(null)" : value.ToString();
        }
    }

    static class TestMain
    {
        static int Main()
        {
            Run("FirmwareTests", FirmwareTests.Run);
            Run("ConfigTests", ConfigTests.Run);
            Run("IntegrationTests", IntegrationTests.Run);
            Console.WriteLine();
            Console.WriteLine("passed: " + T.Passed + "  failed: " + T.Failed + "  skipped: " + T.Skipped);
            // ReadKey throws when stdin is redirected (piped output).
            if (!Console.IsInputRedirected)
            {
                Console.WriteLine("Press any key to exit.");
                Console.ReadKey(true);
            }
            return T.Failed == 0 ? 0 : 1;
        }

        static void Run(string group, Action body)
        {
            try
            {
                body();
            }
            catch (Exception ex)
            {
                T.Failed++;
                Console.WriteLine("FAIL  " + group + " crashed: " + ex.GetType().Name + ": " + ex.Message);
            }
        }
    }
}
