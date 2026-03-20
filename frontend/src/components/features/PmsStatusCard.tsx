'use client';

import { useState, useEffect } from 'react';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { RefreshCw, CheckCircle2, XCircle, Settings } from 'lucide-react';

export default function PmsStatusCard() {
  const [status, setStatus] = useState<{
    status: 'connected' | 'disconnected' | 'loading';
    provider: string;
    lastSync: string;
  }>({
    status: 'loading',
    provider: 'Apaleo',
    lastSync: 'Never',
  });

  const [isSyncing, setIsSyncing] = useState(false);

  const fetchStatus = async () => {
    try {
      const res = await fetch('http://localhost:8000/api/v1/pms/status');
      const data = await res.json();
      setStatus({
        status: data.status,
        provider: data.provider,
        lastSync: data.last_sync,
      });
    } catch (error) {
      setStatus(prev => ({ ...prev, status: 'disconnected' }));
    }
  };

  useEffect(() => {
    fetchStatus();
  }, []);

  const handleSync = async () => {
    setIsSyncing(true);
    try {
      await fetch('http://localhost:8000/api/v1/pms/sync?use_mock=false', {
        method: 'POST',
      });
      // Poll for status update or just wait
      setTimeout(fetchStatus, 2000);
    } catch (error) {
      console.error('Sync failed', error);
    } finally {
      setIsSyncing(false);
    }
  };

  return (
    <div className="rounded-xl border bg-card text-card-foreground shadow-sm">
      <div className="flex flex-col space-y-1.5 p-6">
        <div className="flex items-center justify-between">
          <h3 className="text-xl font-semibold leading-none tracking-tight flex items-center gap-2">
            <Settings className="w-5 h-5 text-muted-foreground" />
            PMS Integration
          </h3>
          <Badge variant={status.status === 'connected' ? 'default' : 'destructive'} className="capitalize">
            {status.status === 'connected' ? (
              <span className="flex items-center gap-1">
                <CheckCircle2 className="w-3 h-3" /> Connected
              </span>
            ) : (
              <span className="flex items-center gap-1">
                <XCircle className="w-3 h-3" /> Disconnected
              </span>
            )}
          </Badge>
        </div>
      </div>
      <div className="p-6 pt-0 space-y-4">
        <div className="grid grid-cols-2 gap-4">
          <div className="space-y-1">
            <p className="text-xs font-medium text-muted-foreground uppercase">Provider</p>
            <p className="text-sm font-semibold capitalize">{status.provider}</p>
          </div>
          <div className="space-y-1">
            <p className="text-xs font-medium text-muted-foreground uppercase">Last Sync</p>
            <p className="text-sm font-semibold">{status.lastSync}</p>
          </div>
        </div>
        
        <div className="pt-2">
          <Button 
            onClick={handleSync} 
            disabled={isSyncing || status.status !== 'connected'}
            className="w-full flex items-center gap-2 transition-all duration-300"
          >
            <RefreshCw className={`w-4 h-4 ${isSyncing ? 'animate-spin' : ''}`} />
            {isSyncing ? 'Syncing Data...' : 'Sync Now'}
          </Button>
          <p className="text-[10px] text-center text-muted-foreground mt-2 italic">
            Synchronizes occupancy and revenue data for the current day.
          </p>
        </div>
      </div>
    </div>
  );
}
