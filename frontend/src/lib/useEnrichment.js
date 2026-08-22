import { useEffect, useRef } from 'react'
import { getEnrichment } from '../api/client'

// How often to ask, and for how long. The two model calls behind an enrichment
// typically land in a handful of seconds; the ceiling exists so a lost backend worker
// can't leave the tab polling forever (the backend independently reports a long-pending
// session as 'failed' — see ENRICHMENT_TIMEOUT_SECONDS).
const POLL_INTERVAL_MS = 2000
const MAX_WAIT_MS = 180000

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
    const startedAt = Date.now()

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
          timer = setTimeout(poll, POLL_INTERVAL_MS)
          return
        }
        if (enrichment.status === 'ready') merge(enrichment)
        stop(enrichment.status === 'ready' ? null : enrichment.status)
      } catch {
        // A dropped request is not a failed enrichment — keep trying until MAX_WAIT_MS.
        if (!cancelled) timer = setTimeout(poll, POLL_INTERVAL_MS)
      }
    }

    timer = setTimeout(poll, POLL_INTERVAL_MS)
    return () => {
      cancelled = true
      if (timer) clearTimeout(timer)
    }
  }, [sessionId, status, setAnalysis])
}
