using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Linq;
using System.Runtime.Serialization.Formatters.Binary;
using System.Text;
using System.Threading.Tasks;
using Windows.ApplicationModel.AppService;
using Windows.Foundation.Collections;

namespace BridgeHandler
{
    internal class AppServiceCommunicator
    {
        private AppServiceConnection _appService;
        private const string APP_SERVICE_NAME = "com.samsung.bridgecom";
        private static readonly string PACKAGE_FAMILY_NAME = Windows.ApplicationModel.Package.Current.Id.FamilyName;
        Random random = new Random();
        StringBuilder logMsg = new StringBuilder();
        int OneMB = 1024 * 1024;
        void WriteLine(String str)
        {
            Console.WriteLine(str);
            //logMsg.AppendLine(str + "\n");
            //if (logMsg.Length > 1000)
            //{
            //    Console.WriteLine(logMsg.ToString());
            //    logMsg.Clear();
            //}
            
        }
        public async Task Init()
        {
            if (_appService == null)
            {
                _appService = new AppServiceConnection
                {
                    AppServiceName = APP_SERVICE_NAME,
                    PackageFamilyName = PACKAGE_FAMILY_NAME
                };
                AppServiceConnectionStatus appServiceStatus = await _appService.OpenAsync();

                if (appServiceStatus == AppServiceConnectionStatus.Success)
                {
                    _appService.RequestReceived += _appService_RequestReceived;
                    _appService.ServiceClosed += _appService_ServiceClosed;                    
                }
                else
                {
                    _appService = null;
                }
            }


        }

        private void _appService_ServiceClosed(AppServiceConnection sender, AppServiceClosedEventArgs args)
        {
            Console.WriteLine("_appService_ServiceClosed");
            _appService = null;
        }

        private void _appService_RequestReceived(AppServiceConnection sender, AppServiceRequestReceivedEventArgs args)
        {
            //Console.WriteLine("_appService_RequestReceived");
            AppServiceDeferral messageDeferral = args.GetDeferral();
            PrintValueSet(args.Request.Message);
            messageDeferral?.Complete();
        }

        public string RandomString(int length)
        {
            const string chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789";
            return new string(Enumerable.Repeat(chars, length)
                .Select(s => s[random.Next(s.Length)]).ToArray());
        }
        //public static byte[] GetBinaryData(int len)
        //{
        //    try
        //    {
        //        using MemoryStream memoryStream = new MemoryStream();
        //        using StreamWriter writer = new StreamWriter(memoryStream);
        //        new BinaryFormatter().Serialize(memoryStream, data);
        //        return memoryStream.ToArray();
        //    }
        //    catch (Exception ex)
        //    {
        //        Console.WriteLine("Serialize() Exception: " + ex.Message);
        //    }

        //    return new byte[0];
        //}

        Process currentProcess;
        long initialMemory = 0;
        double mTotalTime = 0.0;
        double mTotalCPUUsage = 0.0;


        public void printN(int N)
        {
            WriteLine(N + " request at a time");
        }
        public void resetTTime(int N)
        {
            mTotalTime = 0;
            mTotalCPUUsage = 0.0;
            currentProcess = Process.GetCurrentProcess();
            //initialMemory = currentProcess.PrivateMemorySize64;
            initialMemory = GC.GetTotalMemory(false);

            
        }

        public double getTTime(int div, int MBVal)
        {
            //long finalMemory = currentProcess.PrivateMemorySize64;
            long finalMemory = GC.GetTotalMemory(false);
            long memoryUsage = (finalMemory - initialMemory) / (1024 * 1024); // Convert to MB

            WriteLine(((MBVal / OneMB)) + "megabytes Total Execution Time:" + mTotalTime + " millisecond; Average Execution Time: " + (mTotalTime/div) + "millisecond; CPU Usage: " + mTotalCPUUsage + " millisecond; memory usage: " + memoryUsage  + " megabytes; Starting memory: " + (initialMemory/ (1024 * 1024)) + "megabytes; Current memory: " + (finalMemory / (1024 * 1024))+ " megabytes");
            return mTotalTime; 
        }

        
        public async Task SendMsg(String Tes, int MBVal)
        {
            await Init();


            long initialMemory = currentProcess.WorkingSet64;

            TimeSpan cpuBefore = currentProcess.TotalProcessorTime;

            ValueSet request = new ValueSet
                {
                    { "Msg", new byte[MBVal] }
                };

            Stopwatch stopwatch = new Stopwatch();
            stopwatch.Start();

           
            AppServiceResponse response = await _appService.SendMessageAsync(request);
            stopwatch.Stop();
            TimeSpan cpuAfter = currentProcess.TotalProcessorTime;
            double cpuUsage = (cpuAfter - cpuBefore).TotalMilliseconds;
            if (response.Status == AppServiceResponseStatus.Success)
            {
                double epTime = stopwatch.Elapsed.TotalMilliseconds;

                mTotalTime += epTime;
                mTotalCPUUsage += cpuUsage;

                //WriteLine("Execution Time:" + epTime + " mTotalTime: "+ mTotalTime);

                //PrintValueSet(response.Message);
            }
        }

        public async Task SendMsg(int MBVal)
        {
            await Init();
            string line = RandomString(10);
            WriteLine("Sending: " + line);

            Process currentProcess = Process.GetCurrentProcess();
            long initialMemory = currentProcess.WorkingSet64;

            TimeSpan cpuBefore = currentProcess.TotalProcessorTime;


            Stopwatch stopwatch = new Stopwatch();
            stopwatch.Start();

            ValueSet request = new ValueSet
                {
                    { "Msg", new byte[MBVal] }
                };
            AppServiceResponse response = await _appService.SendMessageAsync(request);
            stopwatch.Stop();
            if (response.Status == AppServiceResponseStatus.Success)
            {
                double epTime = stopwatch.Elapsed.TotalMilliseconds;

                long finalMemory = currentProcess.WorkingSet64;
                long memoryUsage = (finalMemory - initialMemory) / (1024 * 1024); // Convert to MB


                TimeSpan cpuAfter = currentProcess.TotalProcessorTime;

                WriteLine((MBVal/ OneMB) + "MB Execution Time:" + epTime  + " Memory usage: "+ memoryUsage + "MB"
                    + " CPU usage: "+ (cpuAfter - cpuBefore).TotalMilliseconds
                    );

                //PrintValueSet(response.Message);
            }
        }

        public async Task SendMsg()
        {
            await Init();            
            string line = RandomString(10);
            WriteLine("Sending: " + line);

            Stopwatch stopwatch = new Stopwatch();
            stopwatch.Start();

            ValueSet request = new ValueSet
                {                    
                    { "Msg", new byte[OneMB * 100] }
                };
            AppServiceResponse response = await _appService.SendMessageAsync(request);
            stopwatch.Stop();
            if (response.Status == AppServiceResponseStatus.Success)
            {
                double epTime = stopwatch.Elapsed.TotalMilliseconds;

                WriteLine("Execution Time:" + epTime);

                //PrintValueSet(response.Message);
            }
        }
        void PrintValueSet(ValueSet s)
        {
            if(s == null)
            {
                Console.WriteLine("ValueSet is null");
                return;
            }
            foreach (var item in s)
            {
                if(item.Value is byte[] data)
                {
                    WriteLine(item.Key.ToString() + " Data Len:" + data.Length);
                }
                else
                {
                    WriteLine(item.Key.ToString() + " " + item.Value.ToString());
                }
                
            }
        }
    }
}
