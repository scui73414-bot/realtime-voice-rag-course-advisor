/**
 * Copyright 2025 Beijing Volcano Engine Technology Co., Ltd. All Rights Reserved.
 * SPDX-license-identifier: BSD-3-Clause
 */

import { useDispatch, useSelector } from 'react-redux';
import { RootState } from '@/store';
import CheckScene from './CheckScene';
import { SceneConfig, updateScene } from '@/store/slices/room';
import { useScene } from '@/lib/useCommon';
import style from './index.module.less';

function AIChangeCard() {
  const { scene, sceneConfigMap } = useSelector((state: RootState) => state.room);
  const dispatch = useDispatch();
  const { icon, isVision } = useScene();
  const Scenes = Object.keys(sceneConfigMap).map(key => sceneConfigMap[key]);

  const handleChecked = (checkedScene: string) => {
    dispatch(updateScene(checkedScene));
  };

  return (
    <div className={style.card}>
      <div className={style.avatar}>
        <img id="avatar-card" src={icon} alt="Avatar" />
      </div>
      <div className={style.title}>
        <div className={style.eyebrow}>知识库增强 · 实时语音</div>
        <div>你好，我是懂小智</div>
        <div className={style.desc}>
          {isVision ? <>支持视觉理解，</> : ''}
          基于课程资料，为你解答学习路线、项目内容与适合人群
        </div>
      </div>
      <div className={style.featureList} aria-label="核心能力">
        <span>实时语音</span>
        <span>课程 RAG</span>
        <span>同步字幕</span>
      </div>
      <div className={style.sceneContainer}>
        {Scenes.map((key: SceneConfig) =>
          <CheckScene
            key={key.name}
            icon={key.icon}
            title={key.name}
            checked={key.id === scene}
            onClick={() => handleChecked(key.id)}
          />
        )}
      </div>
    </div>
  );
}

export default AIChangeCard;
