import { useEffect, useRef } from 'react'
import { getEnrichment } from '../api/client'

// How often to ask, and for how long.
//
// The interval backs off: an enrichment that finishes quickly is caught within a couple
// of seconds, while one waiting on a slow forecast stops costing a request every 2s for
// several minutes. The ceiling has to stay above the backend's own worst case
// (ENRICHMENT_TIMEOUT_SECONDS) — giving up first would strand a result that was about to
// arrive, and the poll is what turns a 'pending' payload into a filled-in forecast.
const POLL_INTERVAL_MS = 2000
const MAX_POLL_INTERVAL_MS = 10000
const POLL_BACKOFF = 1.4
const MAX_WAIT_MS = 600000

/**
 * Folds the LLM-derived half of an analysis into the analysis object once it lands.
 *
 * `POST /api/analyze` answers as soon as the deterministic engines are done, so the
 * dashboard can render real figures immediately, and finishes the demand forecast and
 * the modal-shift suggestions on a background worker. While that is in flight the
 * payload carries `enrichment_status: 'pending'`; this hook polls until it resolves and
 * then merges the result in place, so the forecast and modal-shift views fill in
 * without a second full analysis.
 *
 * Nothing here touches a number: cost, CO2, savings and the recommended actions are
 * final in the first response and are never overwritten.
 *
 * @param analysis   the current analysis payload (or null)
 * @param setAnalysis  state setter to merge the enrichment into
 */
export default function useEnrichment(analysis, setAnalysis) {
  const sessionId = analysis?.session_id
  const status = analysis?.enrichment_status
  // Sessions already resolved in this mount, so a re-render never restarts a poll.
  const settled = useRef(new Set())

  useEffect(() => {
    if (!sessionId || status !== 'pending' || settled.current.has(sessionId)) return

    let cancelled = false
    let timer = null
    let interval = POLL_INTERVAL_MS
    const startedAt = Date.now()

    const scheduleNextPoll = () => {
      timer = setTimeout(poll, interval)
      interval = Math.min(interval * POLL_BACKOFF, MAX_POLL_INTERVAL_MS)
    }

    const merge = (enrichment) => {
      setAnalysis((prev) => {
        // The user may have re-analyzed while this was in flight; that newer run owns
        // the view now, so drop this result rather than pulling stale prose back in.
        if (!prev || prev.session_id !== sessionId) return prev
        return {
          ...prev,
          enrichment_status: enrichment.status,
          summary: {
            ...prev.summary,
            modal_shift_suggestions: enrichment.modal_shift_suggestions || [],
            memos: enrichment.memos || prev.summary?.memos,
          },
          raw_agent_payloads: {
            ...prev.raw_agent_payloads,
            analyst: {
              ...prev.raw_agent_payloads?.analyst,
              output: {
                ...prev.raw_agent_payloads?.analyst?.output,
                modal_shift_suggestions: enrichment.modal_shift_suggestions || [],
              },
            },
            forecaster: {
              ...prev.raw_agent_payloads?.forecaster,
              output: enrichment.forecaster_out || {},
            },
          },
        }
      })
    }

    const stop = (finalStatus) => {
      settled.current.add(sessionId)
      if (finalStatus) {
        setAnalysis((prev) =>
          prev && prev.session_id === sessionId
            ? { ...prev, enrichment_status: finalStatus }
            : prev,
        )
      }
    }

    const poll = async () => {
      if (cancelled) return
      if (Date.now() - startedAt > MAX_WAIT_MS) {
        stop('failed')
        return
      }
      try {
        const enrichment = await getEnrichment(sessionId)
        if (cancelled) return
        if (enrichment.status === 'pending') {
          scheduleNextPoll()
          return
        }
        if (enrichment.status === 'ready') merge(enrichment)
        stop(enrichment.status === 'ready' ? null : enrichment.status)
      } catch {
        // A dropped request is not a failed enrichment — keep trying until MAX_WAIT_MS.
        if (!cancelled) scheduleNextPoll()
      }
    }

    scheduleNextPoll()
    return () => {
      cancelled = true
      if (timer) clearTimeout(timer)
    }
  }, [sessionId, status, setAnalysis])
}
