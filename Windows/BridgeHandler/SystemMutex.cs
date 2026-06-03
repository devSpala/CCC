using System;
using System.Collections.Generic;
using System.Text;

namespace BridgeHandler
{
    public class SystemMutex : IDisposable
    {
        readonly Mutex _mutex;
        bool _disposed = false;
        bool _isLocked = false;
        public bool IsLocalLocked { get => _isLocked; }
        public SystemMutex(string name) : this(false, name) { }
        public SystemMutex(bool initiallyOwned, string name)
        {
            _mutex = new Mutex(initiallyOwned, name);
        }
        ~SystemMutex()
        {
            Dispose(false);
        }
        /// <summary>
        /// Try to accuire mutex with provided timeout miliseconds (default wait indefinitely)
        /// </summary>
        /// <param name="timeOutMiliSeconds">Waiting time in miliseconds, 
        /// default value is System.Threading.Timeout.Infinite (-1) to wait indefinitely
        /// </param>
        /// <param name="throwException"> rethrow exception if occurs, default value is false
        /// </param>
        /// <returns></returns>        
        public bool TryWaitOne(int timeOutMiliSeconds = Timeout.Infinite, bool throwException = false)
        {
            bool result = false;
            try
            {
                result = _mutex.WaitOne(timeOutMiliSeconds);
                _isLocked = true;
            }
            catch (Exception ex)
            {
                //Log.D(this, ex.Message);
                if (throwException)
                {
                    throw;
                }
            }
            return result;
        }
        /// <summary>
        /// Rel
        /// </summary>
        /// <param name="throwException"></param>
        public void ReleaseMutex(bool throwException = false)
        {
            try
            {
                if (_isLocked)
                {
                    _mutex.ReleaseMutex();
                    _isLocked = false;
                }

            }
            catch (Exception ex)
            {
                //Log.D(this, ex.Message);
                if (throwException)
                {
                    throw;
                }
            }
        }
        public void Dispose()
        {
            Dispose(true);
            GC.SuppressFinalize(this);
        }
        protected virtual void Dispose(bool disposing)
        {
            if (!_disposed)
            {
                try
                {
                    ReleaseMutex();
                }
                catch (Exception ex)
                {
                    //Log.D(this, ex.Message);
                }
                if (disposing)
                {
                    _mutex.Dispose();
                }
                _disposed = true;
            }
        }
    }

}
