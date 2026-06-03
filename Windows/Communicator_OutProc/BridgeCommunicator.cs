using System;
using System.Collections.Concurrent;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;
using Windows.ApplicationModel.AppService;
using Windows.ApplicationModel.Background;
using Windows.Foundation.Collections;

namespace Communicator_OutProc
{
    public sealed class BridgeCommunicator : IBackgroundTask
    {
        static ConcurrentDictionary<AppServiceConnection, BackgroundTaskDeferral> taskDefs = new ConcurrentDictionary<AppServiceConnection, BackgroundTaskDeferral>();
        static SynchronizedCollection<AppServiceConnection> appServiceConnections = new SynchronizedCollection<AppServiceConnection>();

        public void Run(IBackgroundTaskInstance taskInstance)
        {
            var def = taskInstance.GetDeferral();
            var appService = taskInstance.TriggerDetails as AppServiceTriggerDetails;
            appServiceConnections.Add(appService.AppServiceConnection);

            taskDefs[appService.AppServiceConnection] = def;
            taskInstance.Canceled += (o, e) =>
            {
                RemoveConnection(appService.AppServiceConnection);
            };
   
            appService.AppServiceConnection.RequestReceived += AppServiceConnection_RequestReceived;
            appService.AppServiceConnection.ServiceClosed += AppServiceConnection_ServiceClosed;

        }

        void RemoveConnection(AppServiceConnection con)
        {
            taskDefs[con].Complete();
            taskDefs.TryRemove(con, out _);
            appServiceConnections.Remove(con);
        }
        private void AppServiceConnection_ServiceClosed(AppServiceConnection sender, AppServiceClosedEventArgs args)
        {
            RemoveConnection(sender);
        }

        private async void AppServiceConnection_RequestReceived(AppServiceConnection sender, AppServiceRequestReceivedEventArgs args)
        {
            AppServiceDeferral messageDeferral = args.GetDeferral();
            ValueSet returnData = new ValueSet();
            returnData.Add("ClientCount", appServiceConnections.Count);
            foreach (var con in appServiceConnections)
            {
                if(con != sender)
                {
                    await con.SendMessageAsync(args.Request.Message);
                }
            }
            await args.Request.SendResponseAsync(returnData);
            messageDeferral.Complete();
        }
    }
}
