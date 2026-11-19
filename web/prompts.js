// Soạn lời nhắc cho video AI (Google Flow) và danh sách ảnh cần đính kèm, dùng chung cho trang Gói shot và Canvas.
(function () {
  // Ảnh cần đính kèm cho một shot (Veo nhận tối đa 3): shot cận chi tiết ưu tiên ảnh phụ kiện, shot khác ưu tiên chân dung.
  // refs[slug] = { portrait: {label, url, have}, props: [{label, url, have}] }
  function attachOf(s, refs) {
    const slugs = Array.isArray(s.characters) ? s.characters : [];
    const portraits = slugs.map((c) => refs[c] && refs[c].portrait).filter((r) => r && r.have);
    const props = slugs.flatMap((c) => (refs[c] ? refs[c].props : []));
    const missing = props.filter((p) => !p.have).map((p) => p.label);
    // Ảnh khóa bối cảnh (refs.__loc[id bối cảnh]) nếu đã có: đặt sau nhân vật, trước phụ kiện ở shot thường.
    const scene = refs.__loc && s._loc && refs.__loc[s._loc] && refs.__loc[s._loc].have ? [refs.__loc[s._loc]] : [];
    const ordered = s.camera === 'insert' ? [...props.filter((p) => p.have), ...portraits, ...scene] : [...portraits, ...scene, ...props.filter((p) => p.have)];
    return { items: ordered.slice(0, 3), cut: ordered.length - Math.min(3, ordered.length), missing };
  }

  // Lời nhắc: mô tả hình (do "đạo diễn" viết, đã có màu chung, bối cảnh, nhân vật) + thoại + chỉ dẫn "nói, không hát".
  function promptOf(s, names, refs) {
    const base = (s.keyframe_prompt || s.action || '').trim();
    const lines = (Array.isArray(s.dialogue) ? s.dialogue : []).map((d) => {
      const who = names[d.character_id] || d.character_id || 'The character';
      return `${who} says one short sentence in Vietnamese in a plain, flat, everyday conversational voice, like casual talk (speaking, NOT singing, no melody, normal speed): "${d.line}" Accurate lip sync, natural subtle expression.`;
    });
    const sound = lines.length ? 'Soft natural ambient sound only, absolutely no music.' : 'Soft natural ambient sound only, no dialogue, no music.';
    // Người nói nhìn người đối diện (ngoài khung hình), không nhìn thẳng ống kính; shot cận chi tiết thì giọng phát ra ngoài khung.
    const gaze = !lines.length ? '' : (s.camera === 'insert'
      ? 'The speaker is off-screen: only the speaker\'s voice is heard, no face is visible, the frame shows only the detail.'
      : 'The speaker looks at the other person just off-camera, never directly into the lens.');
    const useRefs = attachOf(s, refs).items.length
      ? 'Use the attached reference images: the people\'s faces and every accessory (such as the bracelet) must look exactly identical to the references, same shape, color and size, on the same wrist.' : '';
    const night = /night|đêm/i.test(base)
      ? 'It is night time: every window shows darkness with rain and distant street lights, absolutely no daylight and no blue sky.' : '';
    return ['Photorealistic cinematic shot, shot on 35mm film, real people, natural skin texture, no beauty filter.', base, night, useRefs, ...lines, gaze, sound, 'No subtitles, no text on screen.'].filter(Boolean).join('\n');
  }

  window.SFP = { attachOf, promptOf };
})();
