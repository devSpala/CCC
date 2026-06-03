using System;
using System.Collections.Generic;
using System.Text;

namespace BridgeHandler
{
    public class SingleThreadExecutor
    {
        private const string TAG = "SingleThreadExecutor";

        private readonly TaskFactory _taskFactory;

        private string _name = "";
        private bool _isShutdown = false;

        public SingleThreadExecutor(string name, CancellationToken cancellationToken)
        {
            _name = name;
            //_taskFactory = new TaskFactory(new ConcurrentExclusiveSchedulerPair().ExclusiveScheduler);
            _taskFactory = new TaskFactory(cancellationToken);
        }

        public void Run(string caller, Action action)
        {
            //Log.I(TAG, "name: " + _name + ", caller: " + caller);

            if (_isShutdown)
            {
                //CoeditLogger.i(TAG, "ThreadPool is already shutdown, name : " + _name); ;
                return;
            }
            Task task = _taskFactory.StartNew(action);
            ThreadPool.QueueUserWorkItem(async state => await (Task)state, task);
        }

        public void Run(string caller, Action action, CancellationToken cancellationToken)
        {
            int worker;
            int ioCompletion;
            ThreadPool.GetMaxThreads(out worker, out ioCompletion);

            //if (cancellationToken.IsCancellationRequested)
            //{
            //    cancellationToken.ThrowIfCancellationRequested();
            //}

            Task task = _taskFactory.StartNew(action, cancellationToken);

            ThreadPool.QueueUserWorkItem(async state => await (Task)state, task);

        }

        public void shutdown()
        {
            _isShutdown = true;
        }
    }
}
