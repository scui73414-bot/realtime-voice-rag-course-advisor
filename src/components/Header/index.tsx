/**
 * Copyright 2025 Beijing Volcano Engine Technology Co., Ltd. All Rights Reserved.
 * SPDX-license-identifier: BSD-3-Clause
 */

import { Button, Popover } from '@arco-design/web-react';
import { IconMenu } from '@arco-design/web-react/icon';
import NetworkIndicator from '@/components/NetworkIndicator';
import { useIsMobile } from '@/utils/utils';
import styles from './index.module.less';

const Repository = 'https://github.com/scui73414-bot/realtime-voice-rag-course-advisor';
const DeploymentGuide = `${Repository}/blob/main/docs/deployment.md`;
const TestResults = `${Repository}/blob/main/docs/test-results.md`;

interface HeaderProps {
  children?: React.ReactNode;
  hide?: boolean;
}

function Header(props: HeaderProps) {
  const { children, hide } = props;
  const isMobile = useIsMobile();

  const MenuProps = [
    {
      name: 'GitHub 源码',
      url: Repository,
    },
    {
      name: '部署说明',
      url: DeploymentGuide,
    },
    {
      name: '验收记录',
      url: TestResults,
    },
  ];

  return (
    <div
      className={styles.header}
      style={{
        display: hide ? 'none' : 'flex',
      }}
    >
      <div className={styles['header-logo']}>
        {isMobile ? null : (
          <Popover
            content={
              <div className={styles['menu-wrapper']}>
                {MenuProps.map((menuItem) => (
                  <Button
                    type="text"
                    key={menuItem.name}
                    onClick={() => {
                      window.open(menuItem.url, '_blank');
                    }}
                  >
                    {menuItem.name}
                  </Button>
                ))}
              </div>
            }
          >
            <IconMenu className={styles['header-setting-btn']} />
          </Popover>
        )}
        <div className={styles['brand-mark']} aria-hidden="true">懂</div>
        <div className={styles['brand-copy']}>
          <span className={styles['brand-name']}>懂小智</span>
          <span className={styles['brand-subtitle']}>实时语音 AI 课程顾问</span>
        </div>
        <NetworkIndicator />
      </div>
      {children}
      {isMobile ? null : (
        <div className={styles['header-right']}>
          <div
            className={styles['header-right-text']}
            onClick={() => window.open(Repository, '_blank')}
          >
            GitHub 源码
          </div>
          <div
            className={styles['header-right-text']}
            onClick={() => window.open(TestResults, '_blank')}
          >
            项目验收
          </div>
        </div>
      )}
    </div>
  );
}

export default Header;
