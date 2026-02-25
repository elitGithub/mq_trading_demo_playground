<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import { createChart, ColorType } from 'lightweight-charts';
  import type { IChartApi, ISeriesApi, CandlestickData, Time } from 'lightweight-charts';
  import { chartBars, selectedSymbol } from '$lib/stores/market';

  let chartContainer: HTMLDivElement;
  let chart: IChartApi;
  let candleSeries: ISeriesApi<'Candlestick'>;

  function countDecimals(value: number): number {
    if (!Number.isFinite(value)) return 0;
    const s = value.toString().toLowerCase();
    if (s.includes('e-')) {
      const parts = s.split('e-');
      const exp = parseInt(parts[1] || '0', 10);
      return Number.isFinite(exp) ? exp : 0;
    }
    const dot = s.indexOf('.');
    return dot === -1 ? 0 : s.length - dot - 1;
  }

  function resolvePriceFormat(bars: any[]) {
    let maxDecimals = 0;
    for (const b of bars) {
      maxDecimals = Math.max(
        maxDecimals,
        countDecimals(b.open),
        countDecimals(b.high),
        countDecimals(b.low),
        countDecimals(b.close),
      );
    }
    const precision = Math.min(Math.max(maxDecimals, 2), 8);
    const minMove = Math.pow(10, -precision);
    return { precision, minMove };
  }

  onMount(() => {
    chart = createChart(chartContainer, {
      layout: {
        background: { type: ColorType.Solid, color: '#0c0c11' },
        textColor: '#5a5a70',
        fontFamily: "'JetBrains Mono', monospace",
        fontSize: 11,
      },
      grid: {
        vertLines: { color: '#1414192e' },
        horzLines: { color: '#1414192e' },
      },
      width: chartContainer.clientWidth,
      height: chartContainer.clientHeight || 500,
      crosshair: {
        mode: 0,
        vertLine: {
          color: '#6366f140',
          labelBackgroundColor: '#6366f1',
        },
        horzLine: {
          color: '#6366f140',
          labelBackgroundColor: '#6366f1',
        },
      },
      timeScale: {
        timeVisible: true,
        secondsVisible: false,
        borderColor: '#1e1e2a',
      },
      rightPriceScale: {
        borderColor: '#1e1e2a',
      },
    });

    candleSeries = chart.addCandlestickSeries({
      upColor: '#00dc82',
      downColor: '#ff4757',
      borderVisible: false,
      wickUpColor: '#00dc8280',
      wickDownColor: '#ff475780',
    });

    const resizeObserver = new ResizeObserver(() => {
      if (chartContainer) {
        chart.applyOptions({
          width: chartContainer.clientWidth,
          height: chartContainer.clientHeight,
        });
      }
    });
    resizeObserver.observe(chartContainer);

    return () => resizeObserver.disconnect();
  });

  const unsubBars = chartBars.subscribe((bars) => {
    if (candleSeries && bars.length > 0) {
      const { precision, minMove } = resolvePriceFormat(bars);
      candleSeries.applyOptions({
        priceFormat: { type: 'price', precision, minMove },
      });
      const formatted: CandlestickData<Time>[] = bars.map(b => ({
        time: b.time as Time,
        open: b.open,
        high: b.high,
        low: b.low,
        close: b.close,
      }));
      candleSeries.setData(formatted);
      chart.timeScale().fitContent();
    }
  });

  onDestroy(() => {
    unsubBars();
    chart?.remove();
  });

  export function addPriceLine(price: number, color: string, title: string) {
    candleSeries?.createPriceLine({
      price,
      color,
      lineWidth: 1,
      lineStyle: 2,
      axisLabelVisible: true,
      title,
    });
  }
</script>

<div bind:this={chartContainer}
  class="w-full h-full min-h-[400px] rounded-xl overflow-hidden border border-border bg-surface-0">
</div>
