import { useEffect, useState } from 'react'
import { toast } from 'react-hot-toast'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { ScrollArea } from '@/components/ui/scroll-area'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Switch } from '@/components/ui/switch'
import { Label } from '@/components/ui/label'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Plus, Trash2, Edit, Activity } from 'lucide-react'

// Types
interface SignalDefinition {
  id: number
  signal_name: string
  description: string | null
  trigger_condition: TriggerCondition
  enabled: boolean
  created_at: string
  updated_at: string
}

interface TriggerCondition {
  metric?: string
  operator?: string
  threshold?: number
  time_window?: string
  logic?: string
  conditions?: TriggerCondition[]
}

interface SignalPool {
  id: number
  pool_name: string
  signal_ids: number[]
  symbols: string[]
  enabled: boolean
  created_at: string
}

interface SignalTriggerLog {
  id: number
  signal_id: number | null
  pool_id: number | null
  symbol: string
  trigger_value: Record<string, unknown> | null
  triggered_at: string
}

// API functions
const API_BASE = '/api/signals'

async function fetchSignals(): Promise<{ signals: SignalDefinition[]; pools: SignalPool[] }> {
  const res = await fetch(API_BASE)
  if (!res.ok) throw new Error('Failed to fetch signals')
  return res.json()
}

async function createSignal(data: Partial<SignalDefinition>): Promise<SignalDefinition> {
  const res = await fetch(`${API_BASE}/definitions`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
  if (!res.ok) throw new Error('Failed to create signal')
  return res.json()
}

async function updateSignal(id: number, data: Partial<SignalDefinition>): Promise<SignalDefinition> {
  const res = await fetch(`${API_BASE}/definitions/${id}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
  if (!res.ok) throw new Error('Failed to update signal')
  return res.json()
}

async function deleteSignal(id: number): Promise<void> {
  const res = await fetch(`${API_BASE}/definitions/${id}`, { method: 'DELETE' })
  if (!res.ok) throw new Error('Failed to delete signal')
}

async function createPool(data: Partial<SignalPool>): Promise<SignalPool> {
  const res = await fetch(`${API_BASE}/pools`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
  if (!res.ok) throw new Error('Failed to create pool')
  return res.json()
}

async function updatePool(id: number, data: Partial<SignalPool>): Promise<SignalPool> {
  const res = await fetch(`${API_BASE}/pools/${id}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
  if (!res.ok) throw new Error('Failed to update pool')
  return res.json()
}

async function deletePool(id: number): Promise<void> {
  const res = await fetch(`${API_BASE}/pools/${id}`, { method: 'DELETE' })
  if (!res.ok) throw new Error('Failed to delete pool')
}

async function fetchTriggerLogs(poolId?: number, limit = 50): Promise<SignalTriggerLog[]> {
  const params = new URLSearchParams({ limit: String(limit) })
  if (poolId) params.set('pool_id', String(poolId))
  const res = await fetch(`${API_BASE}/logs?${params}`)
  if (!res.ok) throw new Error('Failed to fetch logs')
  const data = await res.json()
  return data.logs
}

// Constants with descriptions for user guidance
const METRICS = [
  { value: 'oi_delta_percent', label: 'OI Delta %', desc: 'Open Interest change %. Positive=inflow, Negative=outflow. Typical threshold: 3-10%' },
  { value: 'cvd', label: 'CVD', desc: 'Cumulative Volume Delta. Positive=buyers dominate, Negative=sellers dominate' },
  { value: 'funding_rate', label: 'Funding Rate', desc: 'Funding rate. Positive=longs pay shorts. Typical threshold: 0.01-0.05%' },
  { value: 'depth_ratio', label: 'Depth Ratio', desc: 'Bid/Ask depth ratio. >1=more bids, <1=more asks. Typical threshold: 1.2-2.0' },
  { value: 'taker_buy_ratio', label: 'Taker Buy Ratio', desc: 'Taker buy volume ratio. >0.5=buyers aggressive. Typical threshold: 0.55-0.7' },
  { value: 'order_imbalance', label: 'Order Imbalance', desc: 'Order book imbalance. Positive=buy pressure, Negative=sell pressure' },
  { value: 'oi', label: 'OI (Absolute)', desc: 'Absolute Open Interest value in USD' },
  { value: 'price_delta_percent', label: 'Price Delta %', desc: 'Price change %. Typical threshold: 1-5%' },
]

const OPERATORS = [
  { value: 'abs_greater_than', label: '|x| > (Absolute)', desc: 'Triggers when absolute value exceeds threshold (ignores direction)' },
  { value: 'greater_than', label: '> (Greater)', desc: 'Triggers when value is greater than threshold' },
  { value: 'less_than', label: '< (Less)', desc: 'Triggers when value is less than threshold' },
  { value: 'equals', label: '= (Equals)', desc: 'Triggers when value equals threshold' },
]

const TIME_WINDOWS = [
  { value: '1m', label: '1 min', desc: 'Very short-term, high noise' },
  { value: '3m', label: '3 min', desc: 'Short-term signals' },
  { value: '5m', label: '5 min', desc: 'Recommended for most signals' },
  { value: '15m', label: '15 min', desc: 'Medium-term, more reliable' },
  { value: '30m', label: '30 min', desc: 'Longer-term trends' },
  { value: '1h', label: '1 hour', desc: 'Major trend changes only' },
]
const SYMBOLS = ['BTC', 'ETH', 'SOL', 'DOGE', 'XRP', 'AVAX', 'LINK', 'ARB']

export default function SignalManager() {
  const [signals, setSignals] = useState<SignalDefinition[]>([])
  const [pools, setPools] = useState<SignalPool[]>([])
  const [logs, setLogs] = useState<SignalTriggerLog[]>([])
  const [loading, setLoading] = useState(true)
  const [activeTab, setActiveTab] = useState('signals')

  // Signal dialog state
  const [signalDialogOpen, setSignalDialogOpen] = useState(false)
  const [editingSignal, setEditingSignal] = useState<SignalDefinition | null>(null)
  const [signalForm, setSignalForm] = useState({
    signal_name: '',
    description: '',
    metric: 'oi_delta_percent',
    operator: 'abs_greater_than',
    threshold: 5,
    time_window: '5m',
    enabled: true,
  })

  // Pool dialog state
  const [poolDialogOpen, setPoolDialogOpen] = useState(false)
  const [editingPool, setEditingPool] = useState<SignalPool | null>(null)
  const [poolForm, setPoolForm] = useState({
    pool_name: '',
    signal_ids: [] as number[],
    symbols: [] as string[],
    enabled: true,
  })

  const loadData = async () => {
    try {
      setLoading(true)
      const data = await fetchSignals()
      setSignals(data.signals)
      setPools(data.pools)
      const logsData = await fetchTriggerLogs()
      setLogs(logsData)
    } catch (err) {
      toast.error('Failed to load signal data')
    } finally {
      setLoading(false)
    }
  }

  // Silent refresh for logs only (no loading state)
  const refreshLogsSilently = async () => {
    try {
      const logsData = await fetchTriggerLogs()
      setLogs(logsData)
    } catch {
      // Silent fail - don't interrupt user
    }
  }

  // Initial load
  useEffect(() => {
    loadData()
  }, [])

  // Auto-refresh logs only when on logs tab (silent, no loading)
  useEffect(() => {
    if (activeTab !== 'logs') return
    const interval = setInterval(refreshLogsSilently, 15000)
    return () => clearInterval(interval)
  }, [activeTab])

  const openSignalDialog = (signal?: SignalDefinition) => {
    if (signal) {
      setEditingSignal(signal)
      const cond = signal.trigger_condition
      setSignalForm({
        signal_name: signal.signal_name,
        description: signal.description || '',
        metric: cond.metric || 'oi_delta_percent',
        operator: cond.operator || 'abs_greater_than',
        threshold: cond.threshold || 5,
        time_window: cond.time_window || '5m',
        enabled: signal.enabled,
      })
    } else {
      setEditingSignal(null)
      setSignalForm({
        signal_name: '',
        description: '',
        metric: 'oi_delta_percent',
        operator: 'abs_greater_than',
        threshold: 5,
        time_window: '5m',
        enabled: true,
      })
    }
    setSignalDialogOpen(true)
  }

  const handleSaveSignal = async () => {
    try {
      const data = {
        signal_name: signalForm.signal_name,
        description: signalForm.description,
        trigger_condition: {
          metric: signalForm.metric,
          operator: signalForm.operator,
          threshold: signalForm.threshold,
          time_window: signalForm.time_window,
        },
        enabled: signalForm.enabled,
      }
      if (editingSignal) {
        await updateSignal(editingSignal.id, data)
        toast.success('Signal updated')
      } else {
        await createSignal(data)
        toast.success('Signal created')
      }
      setSignalDialogOpen(false)
      loadData()
    } catch (err) {
      toast.error('Failed to save signal')
    }
  }

  const handleDeleteSignal = async (id: number) => {
    if (!confirm('Delete this signal?')) return
    try {
      await deleteSignal(id)
      toast.success('Signal deleted')
      loadData()
    } catch (err) {
      toast.error('Failed to delete signal')
    }
  }

  const openPoolDialog = (pool?: SignalPool) => {
    if (pool) {
      setEditingPool(pool)
      setPoolForm({
        pool_name: pool.pool_name,
        signal_ids: pool.signal_ids,
        symbols: pool.symbols,
        enabled: pool.enabled,
      })
    } else {
      setEditingPool(null)
      setPoolForm({ pool_name: '', signal_ids: [], symbols: [], enabled: true })
    }
    setPoolDialogOpen(true)
  }

  const handleSavePool = async () => {
    try {
      if (editingPool) {
        await updatePool(editingPool.id, poolForm)
        toast.success('Pool updated')
      } else {
        await createPool(poolForm)
        toast.success('Pool created')
      }
      setPoolDialogOpen(false)
      loadData()
    } catch (err) {
      toast.error('Failed to save pool')
    }
  }

  const handleDeletePool = async (id: number) => {
    if (!confirm('Delete this pool?')) return
    try {
      await deletePool(id)
      toast.success('Pool deleted')
      loadData()
    } catch (err) {
      toast.error('Failed to delete pool')
    }
  }

  const toggleSymbol = (symbol: string) => {
    setPoolForm(prev => ({
      ...prev,
      symbols: prev.symbols.includes(symbol)
        ? prev.symbols.filter(s => s !== symbol)
        : [...prev.symbols, symbol]
    }))
  }

  const toggleSignalInPool = (signalId: number) => {
    setPoolForm(prev => ({
      ...prev,
      signal_ids: prev.signal_ids.includes(signalId)
        ? prev.signal_ids.filter(id => id !== signalId)
        : [...prev.signal_ids, signalId]
    }))
  }

  const formatCondition = (cond: TriggerCondition) => {
    const metric = METRICS.find(m => m.value === cond.metric)?.label || cond.metric
    const op = OPERATORS.find(o => o.value === cond.operator)?.label || cond.operator
    return `${metric} ${op} ${cond.threshold} (${cond.time_window})`
  }

  if (loading) {
    return <div className="flex items-center justify-center h-64">Loading...</div>
  }

  return (
    <div className="p-4 space-y-4">
      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <div className="flex items-center gap-4 mb-4">
          <TabsList className="justify-start">
            <TabsTrigger value="signals" className="min-w-[100px]">Signals</TabsTrigger>
            <TabsTrigger value="pools" className="min-w-[120px]">Signal Pools</TabsTrigger>
            <TabsTrigger value="logs" className="min-w-[120px]">Trigger Logs</TabsTrigger>
          </TabsList>
          {activeTab === 'signals' && (
            <Button onClick={() => openSignalDialog()} size="sm"><Plus className="w-4 h-4 mr-2" />New Signal</Button>
          )}
          {activeTab === 'pools' && (
            <Button onClick={() => openPoolDialog()} size="sm"><Plus className="w-4 h-4 mr-2" />New Pool</Button>
          )}
        </div>

        <TabsContent value="signals" className="space-y-4">
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
            {signals.map(signal => (
              <Card key={signal.id}>
                <CardHeader className="pb-2">
                  <div className="flex items-center justify-between">
                    <CardTitle className="text-lg">{signal.signal_name}</CardTitle>
                    <div className="flex gap-1">
                      <Button variant="ghost" size="sm" onClick={() => openSignalDialog(signal)}>
                        <Edit className="w-4 h-4" />
                      </Button>
                      <Button variant="ghost" size="sm" onClick={() => handleDeleteSignal(signal.id)}>
                        <Trash2 className="w-4 h-4 text-destructive" />
                      </Button>
                    </div>
                  </div>
                </CardHeader>
                <CardContent>
                  <p className="text-sm text-muted-foreground mb-2">{signal.description}</p>
                  <p className="text-sm font-mono bg-muted p-2 rounded">
                    {formatCondition(signal.trigger_condition)}
                  </p>
                  <div className="flex items-center gap-2 mt-2">
                    <span className={`w-2 h-2 rounded-full ${signal.enabled ? 'bg-green-500' : 'bg-gray-400'}`} />
                    <span className="text-xs">{signal.enabled ? 'Enabled' : 'Disabled'}</span>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        </TabsContent>

        <TabsContent value="pools" className="space-y-4">
          <div className="grid gap-4 md:grid-cols-2">
            {pools.map(pool => (
              <Card key={pool.id}>
                <CardHeader className="pb-2">
                  <div className="flex items-center justify-between">
                    <CardTitle className="text-lg">{pool.pool_name}</CardTitle>
                    <div className="flex gap-1">
                      <Button variant="ghost" size="sm" onClick={() => openPoolDialog(pool)}>
                        <Edit className="w-4 h-4" />
                      </Button>
                      <Button variant="ghost" size="sm" onClick={() => handleDeletePool(pool.id)}>
                        <Trash2 className="w-4 h-4 text-destructive" />
                      </Button>
                    </div>
                  </div>
                </CardHeader>
                <CardContent>
                  <div className="space-y-2">
                    <div>
                      <span className="text-sm font-medium">Symbols: </span>
                      <span className="text-sm">{pool.symbols.join(', ') || 'None'}</span>
                    </div>
                    <div>
                      <span className="text-sm font-medium">Signals: </span>
                      <span className="text-sm">
                        {pool.signal_ids.map(id => signals.find(s => s.id === id)?.signal_name).filter(Boolean).join(', ') || 'None'}
                      </span>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className={`w-2 h-2 rounded-full ${pool.enabled ? 'bg-green-500' : 'bg-gray-400'}`} />
                      <span className="text-xs">{pool.enabled ? 'Enabled' : 'Disabled'}</span>
                    </div>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        </TabsContent>

        <TabsContent value="logs">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Activity className="w-5 h-5" />Trigger History
              </CardTitle>
            </CardHeader>
            <CardContent>
              {logs.length === 0 ? (
                <p className="text-muted-foreground text-center py-8">No triggers recorded yet</p>
              ) : (
                <ScrollArea className="h-[400px]">
                  <div className="space-y-2">
                    {logs.map(log => (
                      <div key={log.id} className="flex items-center justify-between p-2 bg-muted rounded">
                        <div>
                          <span className="font-medium">{log.symbol}</span>
                          <span className="text-sm text-muted-foreground ml-2">
                            Signal #{log.signal_id}
                          </span>
                        </div>
                        <span className="text-sm text-muted-foreground">
                          {new Date(log.triggered_at).toLocaleString()}
                        </span>
                      </div>
                    ))}
                  </div>
                </ScrollArea>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      {/* Signal Dialog */}
      <Dialog open={signalDialogOpen} onOpenChange={setSignalDialogOpen}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>{editingSignal ? 'Edit Signal' : 'New Signal'}</DialogTitle>
            <DialogDescription>Configure when this signal should trigger</DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div>
              <Label>Signal Name</Label>
              <Input
                value={signalForm.signal_name}
                onChange={e => setSignalForm(prev => ({ ...prev, signal_name: e.target.value }))}
                placeholder="e.g., OI Surge Signal"
              />
            </div>
            <div>
              <Label>Description</Label>
              <Input
                value={signalForm.description}
                onChange={e => setSignalForm(prev => ({ ...prev, description: e.target.value }))}
                placeholder="What market condition does this signal detect?"
              />
            </div>
            <div>
              <Label>Metric</Label>
              <Select value={signalForm.metric} onValueChange={v => setSignalForm(prev => ({ ...prev, metric: v }))}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  {METRICS.map(m => <SelectItem key={m.value} value={m.value}>{m.label}</SelectItem>)}
                </SelectContent>
              </Select>
              <p className="text-xs text-muted-foreground mt-1">
                {METRICS.find(m => m.value === signalForm.metric)?.desc}
              </p>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <Label>Operator</Label>
                <Select value={signalForm.operator} onValueChange={v => setSignalForm(prev => ({ ...prev, operator: v }))}>
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>
                    {OPERATORS.map(o => <SelectItem key={o.value} value={o.value}>{o.label}</SelectItem>)}
                  </SelectContent>
                </Select>
                <p className="text-xs text-muted-foreground mt-1">
                  {OPERATORS.find(o => o.value === signalForm.operator)?.desc}
                </p>
              </div>
              <div>
                <Label>Threshold</Label>
                <Input
                  type="number"
                  step="0.1"
                  value={signalForm.threshold}
                  onChange={e => setSignalForm(prev => ({ ...prev, threshold: parseFloat(e.target.value) || 0 }))}
                />
                <p className="text-xs text-muted-foreground mt-1">
                  Value to compare against
                </p>
              </div>
            </div>
            <div>
              <Label>Time Window</Label>
              <Select value={signalForm.time_window} onValueChange={v => setSignalForm(prev => ({ ...prev, time_window: v }))}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  {TIME_WINDOWS.map(tw => <SelectItem key={tw.value} value={tw.value}>{tw.label}</SelectItem>)}
                </SelectContent>
              </Select>
              <p className="text-xs text-muted-foreground mt-1">
                {TIME_WINDOWS.find(tw => tw.value === signalForm.time_window)?.desc}
              </p>
            </div>
            <div className="flex items-center gap-2">
              <Switch checked={signalForm.enabled} onCheckedChange={v => setSignalForm(prev => ({ ...prev, enabled: v }))} />
              <Label>Enabled</Label>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setSignalDialogOpen(false)}>Cancel</Button>
            <Button onClick={handleSaveSignal}>Save</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Pool Dialog */}
      <Dialog open={poolDialogOpen} onOpenChange={setPoolDialogOpen}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>{editingPool ? 'Edit Pool' : 'New Pool'}</DialogTitle>
            <DialogDescription>Configure signal pool</DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div>
              <Label>Pool Name</Label>
              <Input
                value={poolForm.pool_name}
                onChange={e => setPoolForm(prev => ({ ...prev, pool_name: e.target.value }))}
                placeholder="e.g., BTC Momentum Pool"
              />
            </div>
            <div>
              <Label>Symbols</Label>
              <div className="flex flex-wrap gap-2 mt-2">
                {SYMBOLS.map(symbol => (
                  <Button
                    key={symbol}
                    variant={poolForm.symbols.includes(symbol) ? 'default' : 'outline'}
                    size="sm"
                    onClick={() => toggleSymbol(symbol)}
                  >
                    {symbol}
                  </Button>
                ))}
              </div>
            </div>
            <div>
              <Label>Signals</Label>
              <div className="space-y-2 mt-2 max-h-40 overflow-y-auto">
                {signals.map(signal => (
                  <div key={signal.id} className="flex items-center gap-2">
                    <Switch
                      checked={poolForm.signal_ids.includes(signal.id)}
                      onCheckedChange={() => toggleSignalInPool(signal.id)}
                    />
                    <span className="text-sm">{signal.signal_name}</span>
                  </div>
                ))}
              </div>
            </div>
            <div className="flex items-center gap-2">
              <Switch checked={poolForm.enabled} onCheckedChange={v => setPoolForm(prev => ({ ...prev, enabled: v }))} />
              <Label>Enabled</Label>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setPoolDialogOpen(false)}>Cancel</Button>
            <Button onClick={handleSavePool}>Save</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
