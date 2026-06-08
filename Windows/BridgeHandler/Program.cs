using Windows.System.Threading;
using Windows.UI.Core;

namespace BridgeHandler
{
    class Program
    {
        static Mutex _mutex;

        static int OneMB = 1024 * 1024;
        static bool IsSingleInstance()
        {
            try
            {
                // Try to open Existing Mutex.
                //If MyMutex is not opened, then it will throw an exception
                Mutex.OpenExisting("MyMutex");
            }
            catch
            {
                // If exception occurred, there is no such mutex.
                _mutex = new Mutex(true, "MyMutex");
                // Only one instance.
                return true;
            }
            // More than one instance.
            return false;
        }

        static void PrintMenu()
        {
            Console.WriteLine("");
            Console.WriteLine("Press Q to exit");
            Console.WriteLine("Press S to Send Msg");
            Console.WriteLine("");
        }

        public static ThreadPoolTimer RunWithDelay(DispatchedHandler agileCallback, int delayInMs)
        {
            TimeSpan delay = TimeSpan.FromMilliseconds(delayInMs);
            ThreadPoolTimer delayTimer = ThreadPoolTimer.CreateTimer((source) =>
            {
                agileCallback.Invoke();
            }, delay);
            return delayTimer;
        }

        private static async Task HandlePushInBackgroundUtil(int i)
        {
            Console.WriteLine("printing i: " + i);
        }

        private static ThreadPoolTimer pushThreadTimer;
        static async void testw(int i)
        {
            

            //for (int i = 0; i < 10; i++)
            {
                pushThreadTimer?.Cancel();

                pushThreadTimer = RunWithDelay(async () => await HandlePushInBackgroundUtil(i), 1);

                

                //mPushMutex.ReleaseMutex();
            }
        }

        private static SingleThreadExecutor mThreadPool;

        class CatchupRunnable
        {
            public void run(String me)
            {
                //Task.Run(async () =>
                //{
                    Console.Write("Started name: "+ me+"\n");
                    Thread.Sleep(5000);
                    //Task.Delay(5000).Wait();
                    Console.Write("Ended name: " + me + "\n");
                //});
            }

            public void run(String me, CancellationToken cancellationToken)
            {
                Console.Write("Started name: " + me + "\n");
                Thread.Sleep(5000);
                cancellationToken.ThrowIfCancellationRequested();
                Console.Write("Ended name: " + me + "\n");
            }
        }

        static CancellationTokenSource tokenSource;
        //static CancellationToken mCancellationToken;


        static public async Task Main(String[] args)
        {
            //Console.WriteLine("Bridge App Tester");

            //if (!IsSingleInstance())
            //{
            //    Console.WriteLine("More than one instance"); // Exit program.
            //}
            //else

            //mCancellationToken = tokenSource.Token;
            tokenSource = new CancellationTokenSource();

            //mThreadPool = new SingleThreadExecutor("_Single_", tokenSource.Token);


            //mThreadPool.Run("requestCatchup", () =>
            //{
            //    try
            //    {
            //        new CatchupRunnable().run("hi-ari1", tokenSource.Token);
            //    }
            //    catch(Exception ex)
            //    {
            //        Console.Write("asdasdadasd: " + ex.Message + "\n");
            //    }
                
            //});

            //mThreadPool.Run("requestCatchup", () =>
            //{
            //    new CatchupRunnable().run("hi-ari2");
            //});

            //mThreadPool.Run("requestCatchup", () =>
            //{
                

            //    try
            //    {
            //        new CatchupRunnable().run("hi-ari3", tokenSource.Token);
            //    }
            //    catch (Exception ex)
            //    {
            //        Console.Write("asdasdadasd: " + ex.Message + "\n");
            //    }
            //}, tokenSource.Token);

            //tokenSource.Cancel();


            //while (true) ;


            //for (int i = 0; i < 1000000; i++)
            //{
            //    testw(i);
            //}

  

            {

                if (!IsSingleInstance())
                {
                    Console.WriteLine("Instance exists already!");
                    //Close();
                    return;
                }

                Console.WriteLine("One instance"); // Continue with program.

                AppServiceCommunicator communicator = new AppServiceCommunicator();
                communicator.Init().Wait();




                while (true)
                {
                    PrintMenu();
                    try
                    {
                        var keyInfo = Console.ReadKey();
                        Console.Write('\b');
                        if (keyInfo == null || keyInfo.Key == ConsoleKey.Q)
                        {
                            break;
                        }
                        else if (keyInfo.Key == ConsoleKey.S)
                        {
                            //communicator.SendMsg(OneMB).Wait();

                            //communicator.SendMsg(OneMB * 10).Wait();

                            //communicator.SendMsg(OneMB * 100).Wait();

                            //communicator.SendMsg(OneMB * 200).Wait();

                            //communicator.SendMsg(OneMB * 500).Wait();

                            //communicator.SendMsg(OneMB * 1024).Wait();

                            int[] kValues = { 700 };

                            for (int k = 0; k < kValues.Length; k++)
                            {
                                int N = kValues[k];

                                communicator.printN(N);

                                communicator.resetTTime(N);
                                for (int i = 0; i < N; i++)
                                {
                                    communicator.SendMsg("d", OneMB).Wait();
                                }
                                communicator.getTTime(N, OneMB);


                                communicator.resetTTime(N);
                                for (int i = 0; i < N; i++)
                                {
                                    communicator.SendMsg("d", OneMB * 10).Wait();
                                }
                                communicator.getTTime(N, OneMB * 10);


                                communicator.resetTTime(N);
                                for (int i = 0; i < N; i++)
                                {
                                    communicator.SendMsg("d", OneMB * 100).Wait();
                                }
                                communicator.getTTime(N, OneMB * 100);


                                communicator.resetTTime(N);
                                for (int i = 0; i < N; i++)
                                {
                                    communicator.SendMsg("d", OneMB * 200).Wait();
                                }
                                communicator.getTTime(N, OneMB * 200);


                                communicator.resetTTime(N);
                                for (int i = 0; i < N; i++)
                                {
                                    communicator.SendMsg("d", OneMB * 500).Wait();
                                }
                                communicator.getTTime(N, OneMB * 500);

                                communicator.resetTTime(N);
                                for (int i = 0; i < N; i++)
                                {
                                    communicator.SendMsg("d", OneMB * 1024).Wait();
                                }
                                communicator.getTTime(N, OneMB * 1024);
                            }
                        }
                        else if (keyInfo.Key == ConsoleKey.T)
                        {
                            for (int i = 0; i < 10000; i++)
                            {
                                //Thread.Sleep(1);
                                
                                communicator.SendMsg().Wait();
                            }
                            
                            

                        }
                    }
                    catch (Exception ex)
                    {
                        Console.Write(ex.Message);
                    }

                }


            }
        }
    }
}