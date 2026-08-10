/**
 * WebSocket envelope helpers for the rootserver hub contract.
 * @see backapp/docs/camera-settings-contract.md
 */

import { toWireSettings } from './cameraSettings.js'

export function buildParamsMessage(settings) {
  return {
    msgtype: 'params',
    data: toWireSettings(settings),
  }
}

export function buildCtlParamsMessage({ k, v }) {
  return {
    msgtype: 'ctlparams',
    k,
    v,
  }
}

/**
 * Parse an inbound hub message. Returns { msgtype, data } or null if invalid.
 * Unknown types are returned with data so callers can log them.
 */
export function parseInbound(raw) {
  let msg
  try {
    msg = typeof raw === 'string' ? JSON.parse(raw) : raw
  } catch {
    return null
  }
  if (!msg || typeof msg !== 'object' || !msg.msgtype) {
    return null
  }
  return { msgtype: msg.msgtype, data: msg.data, raw: msg }
}

export const INBOUND_TYPES = Object.freeze({
  imgData: 'imgData',
  imgProps: 'imgProps',
  imgStats: 'imgStats',
  sysInfo: 'sysInfo',
  motorInfo: 'motorInfo',
  camTiming: 'camTiming',
})
