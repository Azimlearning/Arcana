'use client';

import { type RefObject, useCallback } from 'react';

import type { PanelLayout } from '@/store/uiStore';

interface Props {
  /** Which pair of panels this handle sits between. */
  which: 'sources-chat' | 'chat-studio';
  layout: PanelLayout;
  containerRef: RefObject<HTMLDivElement>;
  onLayoutChange: (layout: PanelLayout) => void;
}

/** Minimum flex-grow for the chat panel — keeps it always usable. */
const MIN_CHAT = 25;
/** Max flex-grow for sources / studio (prevents chat from disappearing). */
const MAX_SOURCES = 35;
const MAX_STUDIO = 65;
/** Keyboard step size in flex-grow units (~2%). */
const STEP = 2;

/**
 * A 4-px vertical drag handle between two shell panels.
 * Mouse drag and arrow-key nudge both write a PanelLayout override to uiStore
 * (FR-UI-07). Hidden when the adjacent panel is fully collapsed.
 */
export function PanelResizer({ which, layout, containerRef, onLayoutChange }: Props) {
  const handleMouseDown = useCallback(
    (e: React.MouseEvent) => {
      e.preventDefault();
      const startX = e.clientX;
      const startLayout = { ...layout };
      const totalFlex = startLayout.sources + startLayout.chat + startLayout.studio;
      const containerWidth = containerRef.current?.offsetWidth ?? window.innerWidth;

      const onMouseMove = (ev: MouseEvent) => {
        // Convert px delta → flex-unit delta (proportional to total flex sum).
        const delta = ((ev.clientX - startX) / containerWidth) * totalFlex;

        let next: PanelLayout;
        if (which === 'sources-chat') {
          // Clamp sources, then back-calculate from actual chat floor so
          // the total flex sum is always conserved. (CRITICAL-2 fix.)
          const rawSources = Math.max(0, Math.min(MAX_SOURCES, startLayout.sources + delta));
          const consumed = rawSources - startLayout.sources;
          const newChat = Math.max(MIN_CHAT, startLayout.chat - consumed);
          const actualConsumed = startLayout.chat - newChat; // real delta after floor
          const finalSources = startLayout.sources + actualConsumed;
          next = { ...startLayout, sources: finalSources, chat: newChat };
        } else {
          const rawStudio = Math.max(0, Math.min(MAX_STUDIO, startLayout.studio - delta));
          const consumed = startLayout.studio - rawStudio;
          const newChat = Math.max(MIN_CHAT, startLayout.chat + consumed);
          const actualConsumed = newChat - startLayout.chat;
          const finalStudio = startLayout.studio - actualConsumed;
          next = { ...startLayout, chat: newChat, studio: finalStudio };
        }
        onLayoutChange(next);
      };

      const onMouseUp = () => {
        document.removeEventListener('mousemove', onMouseMove);
        document.removeEventListener('mouseup', onMouseUp);
      };

      document.addEventListener('mousemove', onMouseMove);
      document.addEventListener('mouseup', onMouseUp);
    },
    [which, layout, containerRef, onLayoutChange],
  );

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      let next: PanelLayout | null = null;

      if (which === 'sources-chat') {
        if (e.key === 'ArrowLeft') {
          const newSources = Math.max(0, layout.sources - STEP);
          const diff = layout.sources - newSources;
          next = { ...layout, sources: newSources, chat: layout.chat + diff };
        } else if (e.key === 'ArrowRight') {
          const newSources = Math.min(MAX_SOURCES, layout.sources + STEP);
          const diff = newSources - layout.sources;
          const newChat = layout.chat - diff;
          if (newChat >= MIN_CHAT) next = { ...layout, sources: newSources, chat: newChat };
        }
      } else {
        if (e.key === 'ArrowRight') {
          const newStudio = Math.max(0, layout.studio - STEP);
          const diff = layout.studio - newStudio;
          next = { ...layout, studio: newStudio, chat: layout.chat + diff };
        } else if (e.key === 'ArrowLeft') {
          const newStudio = Math.min(MAX_STUDIO, layout.studio + STEP);
          const diff = newStudio - layout.studio;
          const newChat = layout.chat - diff;
          if (newChat >= MIN_CHAT) next = { ...layout, studio: newStudio, chat: newChat };
        }
      }

      if (next) {
        e.preventDefault();
        onLayoutChange(next);
      }
    },
    [which, layout, onLayoutChange],
  );

  // Don't render a handle when the adjacent panel is fully collapsed.
  const isHidden =
    (which === 'sources-chat' && layout.sources === 0) ||
    (which === 'chat-studio' && layout.studio === 0);

  if (isHidden) return null;

  const label =
    which === 'sources-chat'
      ? 'Drag to resize sources panel'
      : 'Drag to resize studio panel';

  const totalFlex = layout.sources + layout.chat + layout.studio;
  const ariaValue = Math.round(
    which === 'sources-chat'
      ? (layout.sources / totalFlex) * 100
      : (layout.studio / totalFlex) * 100,
  );

  return (
    <div
      role="separator"
      aria-orientation="vertical"
      aria-label={label}
      aria-valuenow={ariaValue}
      aria-valuemin={0}
      aria-valuemax={100}
      tabIndex={0}
      className="w-1 flex-shrink-0 cursor-col-resize bg-line hover:bg-accent/30 active:bg-accent/50 focus:outline-none focus:bg-accent/40 transition-colors select-none"
      onMouseDown={handleMouseDown}
      onKeyDown={handleKeyDown}
    />
  );
}
