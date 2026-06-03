using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Runtime.InteropServices.WindowsRuntime;
using System.Threading.Tasks;
using Windows.ApplicationModel;
using Windows.ApplicationModel.AppService;
using Windows.Foundation;
using Windows.Foundation.Collections;
using Windows.UI.Core;
using Windows.UI.Xaml;
using Windows.UI.Xaml.Controls;
using Windows.UI.Xaml.Controls.Primitives;
using Windows.UI.Xaml.Data;
using Windows.UI.Xaml.Input;
using Windows.UI.Xaml.Media;
using Windows.UI.Xaml.Navigation;

// The Blank Page item template is documented at https://go.microsoft.com/fwlink/?LinkId=402352&clcid=0x409

namespace BridgeTest
{
    /// <summary>
    /// An empty page that can be used on its own or navigated to within a Frame.
    /// </summary>
    public sealed partial class MainPage : Page
    {
        private AppServiceConnection _appService;
        private const string APP_SERVICE_NAME = "com.samsung.bridgecom";
        private static readonly string PACKAGE_FAMILY_NAME = Windows.ApplicationModel.Package.Current.Id.FamilyName;

        public async Task RunInMainThreadAsync(DispatchedHandler agileCallback, CoreDispatcherPriority priority = CoreDispatcherPriority.Normal)
        {
            var currentView = (Window.Current == null) ? Windows.ApplicationModel.Core.CoreApplication.MainView : Windows.ApplicationModel.Core.CoreApplication.GetCurrentView();

            if (currentView.CoreWindow.Dispatcher.HasThreadAccess)
            {
                agileCallback?.Invoke();
            }
            else
            {
                await currentView.CoreWindow.Dispatcher.RunAsync(priority, agileCallback);
            }
        }
        private void ScrollToBottom(TextBox textBox)
        {
            var grid = (Grid)VisualTreeHelper.GetChild(textBox, 0);
            for (var i = 0; i <= VisualTreeHelper.GetChildrenCount(grid) - 1; i++)
            {
                object obj = VisualTreeHelper.GetChild(grid, i);
                if (!(obj is ScrollViewer)) continue;
                ((ScrollViewer)obj).ChangeView(0.0f, ((ScrollViewer)obj).ExtentHeight, 1.0f, true);
                break;
            }
        }
        public void PrintLog(String str)
        {
            RunInMainThreadAsync(() =>
            {
                LogView.Text += str + "\n";
                ScrollToBottom(LogView);
            });            
        }
        public MainPage()
        {
            this.InitializeComponent();
        }

        private async void Button_Click(object sender, RoutedEventArgs e)
        {
            await FullTrustProcessLauncher.LaunchFullTrustProcessForCurrentAppAsync();
        }
        async Task Init()
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
        private async void Button_Click_1(object sender, RoutedEventArgs e)
        {
            await Init();
            ValueSet request = new ValueSet
                {
                    { "ClientType", "App" },
                    { "AppID", Guid.NewGuid().ToString() }
                };
            await SendMsg(request);
        }

        async Task SendMsg(String msg)
        {
            ValueSet request = new ValueSet
                {
                    { "AppMsg", msg }                    
                };

            await SendMsg(request);
        }
        async Task SendMsg(ValueSet request)
        {
           
            AppServiceResponse response = await _appService.SendMessageAsync(request);
            if (response.Status == AppServiceResponseStatus.Success)
            {
                PrintValueSet(response.Message);
            }
        }
        private void _appService_ServiceClosed(AppServiceConnection sender, AppServiceClosedEventArgs args)
        {
            _appService = null;
        }

        private void _appService_RequestReceived(AppServiceConnection sender, AppServiceRequestReceivedEventArgs args)
        {
            AppServiceDeferral messageDeferral = args.GetDeferral();
            PrintValueSet(args.Request.Message);
            messageDeferral?.Complete();
        }

        void PrintValueSet(ValueSet s)
        {
            if (s == null)
            {
                PrintLog("ValueSet is null");
                return;
            }
            foreach (var item in s)
            {
                PrintLog(item.Key.ToString() + " " + item.Value.ToString());
            }
        }

        private async void TestRapidMsg(object sender, RoutedEventArgs e)
        {            
            for (int i = 0; i < 10000; i++)
            {
                await SendMsg("" + i);
            }
        }
    }
}
