from PySide6.QtCore import QByteArray, Qt
from PySide6.QtGui import QIcon, QPixmap, QPainter
from PySide6.QtSvg import QSvgRenderer

PATHS = {
 'file': '<path d="M14 2H5v20h14V7z M14 2v6h5"/>',
 'folder': '<path d="M3 7V4h7l2 3h9v13H3z M3 10h18"/>',
 'save': '<path d="M3 3h15l3 3v15H3z M7 3v7h10V3 M7 21v-7h10v7"/>',
 'play': '<path d="M6 3l15 9L6 21z" fill="currentColor" stroke-linejoin="round"/>',
 'settings': '<path d="M9 3h6l1 3 3 1 2 5-2 5-3 1-1 3H9l-1-3-3-1-2-5 2-5 3-1z"/><circle cx="12" cy="12" r="3"/>',
 'export': '<path d="M12 16V2 M7 7l5-5 5 5 M3 14v7h18v-7"/>',
 'cube': '<path d="M12 2L2 7v10l10 5 10-5V7z M2 7l10 5 10-5 M12 12v10"/>',
 'search': '<circle cx="10" cy="10" r="6"/><path d="M15 15l6 6"/>',
 'fit': '<path d="M3 9V3h6 M15 3h6v6 M21 15v6h-6 M9 21H3v-6"/><circle cx="12" cy="12" r="4"/>',
 'orbit': '<ellipse cx="12" cy="12" rx="10" ry="5" transform="rotate(-35 12 12)"/><path d="M17 2l3 1-1 4"/><circle cx="12" cy="12" r="2"/>',
 'cursor': '<path d="M4 2l15 12-8 1-3 7z" fill="currentColor"/>',
 'addnode': '<circle cx="8" cy="12" r="5"/><path d="M18 5v14 M12 12h12"/>',
 'bar': '<path d="M4 20L20 4"/><circle cx="4" cy="20" r="2"/><circle cx="20" cy="4" r="2"/>',
 'check': '<path d="M5 12l4 5L20 6"/>',
 'chart': '<path d="M3 21V13h4v8 M10 21V7h4v14 M17 21V3h4v18"/>',
 'weight': '<path d="M6 8h12l3 13H3z"/><circle cx="12" cy="5" r="3"/>',
 'move': '<path d="M12 2v20 M2 12h20 M8 6l4-4 4 4 M8 18l4 4 4-4 M6 8l-4 4 4 4 M18 8l4 4-4 4"/>',
 'code': '<path d="M8 6l-6 6 6 6 M16 6l6 6-6 6 M14 3l-4 18"/>',
 'load': '<path d="M12 2v19 M6 15l6 6 6-6"/>',
 'trash': '<path d="M3 6h18 M8 6V3h8v3 M5 6l1 16h12l1-16 M9 10v8 M15 10v8"/>',
 'stop': '<rect x="5" y="5" width="14" height="14" rx="2"/>',
 'image': '<rect x="3" y="3" width="18" height="18" rx="3"/><circle cx="8" cy="8" r="2"/><path d="M3 17l6-5 4 3 4-5 4 7"/>',
 'link': '<path d="M9 8L5 8a4 4 0 000 8h4 M15 8h4a4 4 0 010 8h-4 M8 12h8"/>',
 'info': '<circle cx="12" cy="12" r="10"/><path d="M12 10v7 M12 6v1"/>'
}


def icon(name, color='#526783', size=24):
    path = PATHS.get(name, PATHS['cube']).replace('currentColor',color)
    svg = f'<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="1.65" stroke-linecap="round" stroke-linejoin="round">{path}</svg>'
    pix = QPixmap(size*2, size*2)
    pix.fill(Qt.transparent)
    p = QPainter(pix)
    QSvgRenderer(QByteArray(svg.encode())).render(p)
    p.end()
    pix.setDevicePixelRatio(2)
    return QIcon(pix)
