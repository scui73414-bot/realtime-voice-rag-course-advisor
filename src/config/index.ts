/**
 * Copyright 2025 Beijing Volcano Engine Technology Co., Ltd. All Rights Reserved.
 * SPDX-license-identifier: BSD-3-Clause
 */

export const Disclaimer = 'https://www.volcengine.com/docs/6348/68916';
export const ReversoContext = 'https://www.volcengine.com/docs/6348/68918';
export const UserAgreement = 'https://www.volcengine.com/docs/6348/128955';

/**
 * @note 本地开发时 FastAPI 使用 3001 端口；生产构建由 FastAPI 同域托管，
 *       因此默认复用当前 HTTPS origin。也可在构建时通过
 *       REACT_APP_API_BASE_URL 显式覆盖。
 */
const configuredApiHost = process.env.REACT_APP_API_BASE_URL?.replace(/\/$/, '');
const isLocalDevelopment =
  ['127.0.0.1', 'localhost'].includes(window.location.hostname) &&
  window.location.port === '4173';

export const AIGC_PROXY_HOST =
  configuredApiHost ||
  (isLocalDevelopment
    ? `${window.location.protocol}//${window.location.hostname}:3001`
    : window.location.origin);

export interface IScene {
  icon: string;
  name: string;
  questions: string[];
  agentConfig: Record<string, any>;
  llmConfig: Record<string, any>;
  asrConfig: Record<string, any>;
  ttsConfig: Record<string, any>;
}
