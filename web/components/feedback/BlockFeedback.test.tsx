// DOM interaction test: click-through voting, single-vote lock, and that
// fetch failures never surface to the user (fire-and-forget analytics).

import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { BlockFeedback } from './BlockFeedback';

describe('BlockFeedback', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(null, { status: 200 })));
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('renders nothing when not ready', () => {
    const { container } = render(
      <BlockFeedback blockId="b1" blockType="CitedSummary" sessionId="s1" ready={false} />
    );
    expect(container).toBeEmptyDOMElement();
  });

  it('posts a rating and highlights the clicked button on thumbs up', async () => {
    const user = userEvent.setup();
    render(<BlockFeedback blockId="b1" blockType="CitedSummary" sessionId="s1" />);

    await user.click(screen.getByLabelText('Thumbs up'));

    expect(fetch).toHaveBeenCalledTimes(1);
    const [url, init] = (fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(String(url)).toMatch(/\/feedback\/rating$/);
    expect(JSON.parse(init.body)).toEqual({
      sessionId: 's1',
      blockId: 'b1',
      rating: 'up',
      blockType: 'CitedSummary',
    });
    expect(screen.getByLabelText('Thumbs up')).toBeDisabled();
    expect(screen.getByLabelText('Thumbs down')).toBeDisabled();
  });

  it('locks after the first vote — a second click does not fire again', async () => {
    const user = userEvent.setup();
    render(<BlockFeedback blockId="b1" blockType="CitedSummary" sessionId="s1" />);

    await user.click(screen.getByLabelText('Thumbs down'));
    await user.click(screen.getByLabelText('Thumbs up')); // disabled — should be a no-op

    expect(fetch).toHaveBeenCalledTimes(1);
  });

  it('swallows a fetch failure without throwing or blocking the vote UI', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('network down')));
    const user = userEvent.setup();
    render(<BlockFeedback blockId="b1" blockType="CitedSummary" sessionId="s1" />);

    await user.click(screen.getByLabelText('Thumbs up'));

    expect(screen.getByLabelText('Thumbs up')).toBeDisabled();
  });
});
