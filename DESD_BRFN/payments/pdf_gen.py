# payments/pdf_generator.py
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
)
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
import io
from django.utils import timezone
from datetime import datetime

def generate_settlement_pdf(settlement, orders):
    """
    Generate PDF for a single settlement
    """
    buffer = io.BytesIO()
    
    try:
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            topMargin=2*cm,
            bottomMargin=2*cm,
            leftMargin=2*cm,
            rightMargin=2*cm
        )
        
        # Styles
        styles = getSampleStyleSheet()
        
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=16,
            alignment=TA_CENTER,
            spaceAfter=20,
            textColor=colors.HexColor('#2c7a4d')
        )
        
        heading_style = ParagraphStyle(
            'Heading',
            parent=styles['Heading2'],
            fontSize=12,
            spaceAfter=10,
            textColor=colors.black
        )
        
        # Style for summary card titles
        card_title_style = ParagraphStyle(
            'CardTitle',
            parent=styles['Normal'],
            fontSize=10,
            alignment=TA_CENTER,
            textColor=colors.grey
        )
        
        # Style for summary card values
        card_value_style = ParagraphStyle(
            'CardValue',
            parent=styles['Normal'],
            fontSize=16,
            alignment=TA_CENTER,
            textColor=colors.black
        )
        
        # Style for payout value (green)
        payout_style = ParagraphStyle(
            'PayoutValue',
            parent=styles['Normal'],
            fontSize=16,
            alignment=TA_CENTER,
            textColor=colors.HexColor('#28a745')
        )
        
        story = []
        
        # ==========================================
        # HEADER
        # ==========================================
        story.append(Paragraph("Bristol Regional Food Network", title_style))
        story.append(Paragraph("Weekly Settlement Statement", heading_style))
        story.append(Spacer(1, 10))
        
        # ==========================================
        # SETTLEMENT INFO TABLE
        # ==========================================
        info_data = [
            [Paragraph("Settlement ID:", styles['Normal']), Paragraph(f"#{settlement.id}", styles['Normal'])],
            [Paragraph("Producer:", styles['Normal']), Paragraph(settlement.producer.business_name, styles['Normal'])],
            [Paragraph("Tax Year:", styles['Normal']), Paragraph(settlement.tax_year, styles['Normal'])],
            [Paragraph("Period:", styles['Normal']), Paragraph(f"{settlement.week_start.strftime('%d %B %Y')} - {settlement.week_end.strftime('%d %B %Y')}", styles['Normal'])],
            [Paragraph("Status:", styles['Normal']), Paragraph(settlement.get_settlement_status_display(), styles['Normal'])],
            [Paragraph("Generated:", styles['Normal']), Paragraph(datetime.now().strftime('%d %B %Y %H:%M'), styles['Normal'])],
        ]
        
        info_table = Table(info_data, colWidths=[3*cm, 10*cm])
        info_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
            ('ALIGN', (1, 0), (1, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ]))
        story.append(info_table)
        story.append(Spacer(1, 20))
        
        # ==========================================
        # SUMMARY CARDS
        # ==========================================
        # Create formatted Paragraphs for each card
        card1 = [
            Paragraph("Total Orders", card_title_style),
            Spacer(1, 5),
            Paragraph(str(settlement.total_orders), card_value_style)
        ]
        
        card2 = [
            Paragraph("Total Sales", card_title_style),
            Spacer(1, 5),
            Paragraph(f"£{settlement.total_subtotal:,.2f}", card_value_style)
        ]
        
        card3 = [
            Paragraph("Commission (5%)", card_title_style),
            Spacer(1, 5),
            Paragraph(f"£{settlement.total_commission:,.2f}", card_value_style)
        ]
        
        card4 = [
            Paragraph("Your Payout", card_title_style),
            Spacer(1, 5),
            Paragraph(f"£{settlement.total_payout:,.2f}", payout_style)
        ]
        
        # Create a table for the summary cards
        summary_data = [[card1, card2, card3, card4]]
        
        summary_table = Table(summary_data, colWidths=[4.5*cm, 4.5*cm, 4.5*cm, 4.5*cm])
        summary_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('BOX', (0, 0), (-1, -1), 1, colors.grey),
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f8f9fa')),
            ('TOPPADDING', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
        ]))
        story.append(summary_table)
        story.append(Spacer(1, 20))
        
        # ==========================================
        # ORDER DETAILS TABLE
        # ==========================================
        if orders:
            story.append(Paragraph("Order Details", heading_style))
            story.append(Spacer(1, 5))
            
            # Table headers
            order_data = [
                [
                    Paragraph("<b>Order ID</b>", styles['Normal']),
                    Paragraph("<b>Date</b>", styles['Normal']),
                    Paragraph("<b>Customer</b>", styles['Normal']),
                    Paragraph("<b>Postcode</b>", styles['Normal']),
                    Paragraph("<b>Subtotal</b>", styles['Normal']),
                    Paragraph("<b>Commission</b>", styles['Normal']),
                    Paragraph("<b>Payout</b>", styles['Normal']),
                ]
            ]
            
            # Add order rows
            for order in orders:
                order_data.append([
                    Paragraph(f"#{order.order_id}", styles['Normal']),
                    Paragraph(order.order_completed_at.strftime('%d %b %Y') if order.order_completed_at else '', styles['Normal']),
                    Paragraph((order.customer_name or 'Anonymous')[:30], styles['Normal']),
                    Paragraph((order.customer_postcode or '—')[:10], styles['Normal']),
                    Paragraph(f"£{order.order_subtotal:,.2f}", styles['Normal']),
                    Paragraph(f"£{order.order_commission:,.2f}", styles['Normal']),
                    Paragraph(f"£{order.order_payout:,.2f}", styles['Normal'])
                ])
            
            # Add totals row
            order_data.append([
                Paragraph("<b>Totals</b>", styles['Normal']),
                Paragraph("", styles['Normal']),
                Paragraph("", styles['Normal']),
                Paragraph("", styles['Normal']),
                Paragraph(f"<b>£{settlement.total_subtotal:,.2f}</b>", styles['Normal']),
                Paragraph(f"<b>£{settlement.total_commission:,.2f}</b>", styles['Normal']),
                Paragraph(f"<b>£{settlement.total_payout:,.2f}</b>", styles['Normal'])
            ])
            
            col_widths = [2.5*cm, 2.5*cm, 4*cm, 2.5*cm, 2.5*cm, 2.5*cm, 2.5*cm]
            
            order_table = Table(order_data, colWidths=col_widths, repeatRows=1)
            order_table.setStyle(TableStyle([
                ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#e9ecef')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
                ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
                ('ALIGN', (4, 1), (6, -1), 'RIGHT'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('GRID', (0, 0), (-1, -2), 0.5, colors.grey),
                ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#f8f9fa')),
                ('TOPPADDING', (0, 0), (-1, -1), 6),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ]))
            story.append(order_table)
        
        # ==========================================
        # FOOTER
        # ==========================================
        story.append(Spacer(1, 30))
        footer_text = Paragraph(
            "This is an official payment settlement statement from Bristol Regional Food Network.<br/>"
            "For any queries, please contact finance@bristolfoodnetwork.com<br/>"
            f"UK Tax Year: {settlement.tax_year}",
            ParagraphStyle(
                'Footer',
                parent=styles['Normal'],
                fontSize=8,
                alignment=TA_CENTER,
                textColor=colors.grey
            )
        )
        story.append(footer_text)
        
        # Build PDF
        doc.build(story)
        
    except Exception as e:
        buffer.write(f"PDF generation failed: {str(e)}".encode())
    
    finally:
        buffer.seek(0)
    
    return buffer