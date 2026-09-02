import { fireEvent, render, screen, within } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import SectionEditor from './SectionEditor';

const dt = { setData: vi.fn(), effectAllowed: '' };

function dragAt(el: HTMLElement, type: 'dragover' | 'drop', clientY: number, clientX = 0) {
  fireEvent(el, new MouseEvent(type, { bubbles: true, cancelable: true, clientY, clientX }));
}

describe('SectionEditor inline lists', () => {
  it('renders skills side by side', () => {
    render(
      <SectionEditor
        kind="skills"
        content={[{ group: 'Lang', skills: ['Python'] }]}
        onChange={vi.fn()}
      />,
    );

    const list = screen.getByDisplayValue('Python').closest('.list') as HTMLElement;
    expect(list.classList).toContain('list-inline');
  });

  it('renders contact links side by side', () => {
    render(
      <SectionEditor
        kind="contact"
        content={{ links: [{ name: 'GitHub', url: 'x' }] }}
        onChange={vi.fn()}
      />,
    );

    const list = screen.getByDisplayValue('GitHub').closest('.list') as HTMLElement;
    expect(list.classList).toContain('list-inline');
  });

  it('keeps bullet points stacked vertically', () => {
    render(
      <SectionEditor
        kind="experience"
        content={[{ bullets: ['A bullet'] }]}
        onChange={vi.fn()}
      />,
    );

    const list = screen.getByDisplayValue('A bullet').closest('.list') as HTMLElement;
    expect(list.classList).not.toContain('list-inline');
  });
});

describe('SectionEditor drag reorder', () => {
  it('reorders skills rows via the grip', () => {
    const onChange = vi.fn();
    render(
      <SectionEditor
        kind="skills"
        content={[{ group: 'Lang', skills: ['Python', 'Go'] }]}
        onChange={onChange}
      />,
    );

    const first = screen.getByDisplayValue('Python').closest('.list-item') as HTMLElement;
    const second = screen.getByDisplayValue('Go').closest('.list-item') as HTMLElement;
    fireEvent.dragStart(within(first).getByTitle('Drag to reorder'), { dataTransfer: dt });
    dragAt(second, 'dragover', 0, 100); // jsdom rects are zero, so 100 is right half
    dragAt(second, 'drop', 0, 100);

    expect(onChange).toHaveBeenCalledWith([{ group: 'Lang', skills: ['Go', 'Python'] }]);
  });

  it('reorders entry rows via the grip', () => {
    const onChange = vi.fn();
    render(
      <SectionEditor
        kind="projects"
        content={[{ title: 'A' }, { title: 'B' }]}
        onChange={onChange}
      />,
    );

    const first = screen.getByDisplayValue('A').closest('.entry') as HTMLElement;
    const second = screen.getByDisplayValue('B').closest('.entry') as HTMLElement;
    fireEvent.dragStart(within(second).getByTitle('Drag to reorder'), { dataTransfer: dt });
    dragAt(first, 'dragover', 0); // top half
    dragAt(first, 'drop', 0);

    expect(onChange).toHaveBeenCalledWith([{ title: 'B' }, { title: 'A' }]);
  });

  it('reorders contact link rows via the grip', () => {
    const onChange = vi.fn();
    render(
      <SectionEditor
        kind="contact"
        content={{
          name: 'Jane',
          links: [
            { name: 'GitHub', url: 'x' },
            { name: 'Site', url: 'y' },
          ],
        }}
        onChange={onChange}
      />,
    );

    const first = screen.getByDisplayValue('GitHub').closest('.list-item') as HTMLElement;
    const second = screen.getByDisplayValue('Site').closest('.list-item') as HTMLElement;
    fireEvent.dragStart(within(first).getByTitle('Drag to reorder'), { dataTransfer: dt });
    dragAt(second, 'dragover', 0, 100); // right half
    dragAt(second, 'drop', 0, 100);

    expect(onChange).toHaveBeenCalledWith({
      name: 'Jane',
      links: [
        { name: 'Site', url: 'y' },
        { name: 'GitHub', url: 'x' },
      ],
    });
  });
});

describe('SectionEditor unlabeled lists', () => {
  it('renders bullets without a label', () => {
    render(
      <SectionEditor kind="experience" content={[{ bullets: ['A bullet'] }]} onChange={vi.fn()} />,
    );
    const list = screen.getByDisplayValue('A bullet').closest('.list') as HTMLElement;
    expect(list.classList).toContain('bullet-list');
    expect(screen.queryByLabelText('Bullet points')).not.toBeInTheDocument();
  });

  it('renders skill items without a label', () => {
    render(
      <SectionEditor
        kind="skills"
        content={[{ group: 'Lang', skills: ['Python'] }]}
        onChange={vi.fn()}
      />,
    );
    expect(screen.getByDisplayValue('Python')).toBeInTheDocument();
    expect(screen.queryByLabelText('Skills')).not.toBeInTheDocument();
  });
});
