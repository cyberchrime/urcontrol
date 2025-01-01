import threading
import time

class UR44C():
    '''
        "F043103E14000402F7" - Keepalive
        "F043103E14010100pppp0000ccvvvvvvvvvvF7" - Change Parameter
        "F043303E1401040200pppp0000ccF7" - Query Parameter
        "F043103E1401040200pppp0000ccvvvvvvvvvvF7 - Reply Parameter
        "F043103E140203........" - Reply Meter Status
    '''


    def __init__(self, midi_in, midi_out):
        self.midi_in = midi_in
        self.midi_in.ignore_types(sysex=False)
        self.midi_in.set_callback(self._midi_callback, self)
        time.sleep(0.1)

        self.midi_out = midi_out
        self.received_params = {}
        self.received_param_event = threading.Event()


    def _sysex_parser(self, message):
        #change parameter message
        if len(message)==19 and message[:8]==[0xF0, 0x43, 0x10, 0x3E, 0x14, 0x01, 0x01, 0x00]:
            param = message[8]*128 + message[9]
            channel = message[12]
            v32 = message[13]*(128**4) + message[14]*(128**3) + message[15]*(128**2) + message[16]*128 + message[17]
            value = (v32 & 0x7FFFFFFF) - (v32 & 0x80000000)
            return {
                'type': 'change-parameter',
                'channel': channel,
                'param': param,
                'value': value,
            }
        #query parameter message
        elif len(message)==15 and message[:9]==[0xF0, 0x43, 0x30, 0x3E, 0x14, 0x01, 0x04, 0x02, 0x00]:
            param = message[9]*128 + message[10]
            channel = message[13]
            return {
                'type': 'query-parameter',
                'channel': channel,
                'param': param,
            }
        #reply parameter message
        elif len(message)==20 and message[:9]==[0xF0, 0x43, 0x10, 0x3E, 0x14, 0x01, 0x04, 0x02, 0x00]:
            param = message[9]*128 + message[10]
            channel = message[13]
            v32 = message[14]*(128**4) + message[15]*(128**3) + message[16]*(128**2) + message[17]*128 + message[18]
            value = (v32 & 0x7FFFFFFF) - (v32 & 0x80000000)
            # print('DEBUG, PARSED PARAM', channel, param, value)
            return {
                'type': 'reply-parameter',
                'channel': channel,
                'param': param,
                'value': value,
            }
        #keepalive
        elif message==[0xF0, 0x43, 0x10, 0x3E, 0x14, 0x00, 0x04, 0x02, 0xF7]:
            return {'type': 'keepalive'}

        #meters
        elif message[0:7] == [240, 67, 16, 62, 20, 2, 3]:
            # parsear mensaje
            # print('entered')
            self.meters = self.parse_meters(message)
            return {'type': 'meters'}

        return {'type': 'unknown'}


    def _midi_callback(self, event, obj=None):
        message, timestamp = event
        res = self._sysex_parser(message)
        if res['type']=='reply-parameter':
            obj.received_params[(res['channel'], res['param'])] = res['value']
            obj.received_param_event.set()


    def parse_meters(self, message):
        meter_array = []
        for i in range(0,47):
            curr_v0 = message[7+4*i+0]
            curr_v1 = message[7+4*i+1]
            peak_v0 = message[7+4*i+2]
            peak_v1 = message[7+4*i+3]

            curr_v0 = curr_v0-128 if curr_v0 > 64 else curr_v0
            curr_val = curr_v0*128 + curr_v1

            peak_v0 = peak_v0-128 if peak_v0 > 64 else peak_v0
            peak_val = peak_v0*128 + peak_v1

            meter_array.append({'index':i,'value':curr_val, 'peak': peak_val})

        return meter_array


    def MIDISendChangeParameterValue(self, parameter, value, channel=0):
        p0 = (parameter >> 7*0) & 0x7F
        p1 = (parameter >> 7*1) & 0x7F
        v32 = value & 0xFFFFFFFF
        v0 = (v32 >> 7*0) & 0x7F
        v1 = (v32 >> 7*1) & 0x7F
        v2 = (v32 >> 7*2) & 0x7F
        v3 = (v32 >> 7*3) & 0x7F
        v4 = (v32 >> 7*4) & 0x7F
        message = [0xF0, 0x43, 0x10, 0x3E, 0x14, 0x01, 0x01, 0x00, p1, p0, 0x00, 0x00, channel, v4, v3, v2, v1, v0, 0xF7]
        self.midi_out.send_message(message)


    def MIDISendQueryParameterValue(self, parameter, channel=0):
        p0 = (parameter >> 7*0) & 0x7F
        p1 = (parameter >> 7*1) & 0x7F
        message = [0xF0, 0x43, 0x30, 0x3E, 0x14, 0x01, 0x04, 0x02, 0x00, p1, p0, 0x00, 0x00, channel, 0xF7]
        self.midi_out.send_message(message)


    def SendKeepalive(self):
        message = [0xF0, 0x43, 0x10, 0x3E, 0x14, 0x00, 0x04, 0x02, 0xF7]
        self.midi_out.send_message(message)


    def SetParameter(self, parameter, value, channel=0, confirm=True, confirm_timeout=3):
        self.MIDISendChangeParameterValue(parameter, value, channel)
        if confirm:
            self.received_params.pop((channel, parameter), None)
            self.received_param_event.clear()
            self.MIDISendQueryParameterValue(parameter, channel)
            if self.received_param_event.wait(confirm_timeout):
                received_value = self.received_params.pop((channel, parameter), None)
                self.received_param_event.clear()
                if received_value == value:
                    return True
            return False
        else:
            return True

    def GetParameter(self, parameter, channel=0, check_timeout=3):
        self.received_params.pop((channel, parameter), None)
        self.received_param_event.clear()
        self.MIDISendQueryParameterValue(parameter, channel)

        if self.received_param_event.wait(check_timeout):
            received_value = self.received_params.pop((channel, parameter), None)
            self.received_param_event.clear()
            return received_value
        return None

    def SetParameterByName(self, unit, name, value, input=0):
        param_num, min_val, max_val, def_val, val_descr, notes = getattr(unit, name)
        assert min_val <= value <= max_val
        assert 0 <= input <= 5
        return self.SetParameter(param_num, value, input)

    def GetParameterByName(self, unit, name, input=0):
        param_num, min_val, max_val, def_val, val_descr, notes = getattr(unit, name)
        assert 0 <= input <= 5
        return self.GetParameter(param_num, input)


    def ResetConfig(self):
        message = bytes.fromhex(initialize_bulk_message)
        # self.midi_out.send_message(message)

        # somehow rtmidi not work with large sysex. Use amidi as workaround
        open('/tmp/reset.syx', 'wb').write(message)
        os.system('amidi --p hw:2,0,1 -s /tmp/reset.syx')




initialize_bulk_message ="""
F043003E2D6F1401010000000001465F4375727265006E745363656E650000000000000000000000005B27000008640500000001000406000701010008000101
0050010100085101010001000148001101010012010001005A0101005B1101010001000200107201010073010144007401010075012201000100060000200101
00010101000002010100030101000004010100310102010032010100331101010034010100083501010036010144003701010009012001000A01010052010101
0053010100080B0101000C010100000D0101005401020100550101000E100101000F000100001000010056000104005700010001002401001301010014000101
005C010100085D0101001501014000160101005E010201005F010100171000010018000100006000010061000144000100060051404001000400524001000100
00010036001053010200540102000055010100560100010057010100580001010059010100005A0102005B010100005C0101005D010002005E0101005F000102
0060010100006101010062010200006301020001000406002A01010036000101002B010100002C0101002D010200002E0102002F010001003001010031000101
00320101000047010100330101400034010200350100010037010100440101010038010100003901020045010104003A0101003B010002003C01010046010101
003D010100003E0102003F0102000001000100400140010041010100420001010043010100004401010045010100004601010047010001004801010049000101
004A010100004B0101004C010100004D0101004E010001006A0101006B110101004F01010000500101006C010104006D01010102012001010301020104000101
0105010100010100020065010100006601010067010001006801010069000101006A010100006B0101006C010100006D0101006E010001006F01010070000101
0071010100007201010073010100007401010075010001007601010077000101007801010000790101007A010100007B0101007C010001007D0101007E000101
007F010100000001010001010144000201010003012201000401010005110101000601010008070101000801014400090101000A012201000B0101000C110101
000D010100080E0101000F010144001001010011012201001201010013110101001401010008150101001601014400170101001801220100190101001A110101
001B010100081C0101001D010144001E0101001F0122010020010100211101010022010100082301010024010144002501010026012201002701010028110101
0029010100082A0101002B010144002C0101002D012201002E010100481101010049010100084A0101004B010244004C0101004D012202004E01010001120001
001C010100001D0101006401010400650101001E012001001F010100660101010067010100082000010021000100006800010069002201000100010025200101
0001000100103E0104003F010444006E0104006F012204004001040041110104007001040008710104015A010440015B0104015C010004015D01040001020002
007601010008770101007801014400790101007A012201007B0101007C110101007D010100087E0001007F000144010000010101000001000100060106200101
010701010100080101000100030801090101010A010001010B01010001020001010C010101000D0101010E01010000010001010F014001011000020111000101
01120002010013010101140101000115010101160100010117010101180001010119010101001A0101011B010100011C0101011D010001011E0101011F000101
0120010101002101010122010100012301010124010001012501010126000101012701010100280101000100020801290101012A010001012B0101012C000101
012D010101002E0102012F0101000130010200010004020131010101320001010133010101003401010135010100013601020137010002013801010139000101
013A01010001010002013B010100013C0101013D010001013E0101013F0001010140010101004101020142010100014301020001000401014401010145000101
014601010100470101014801010001490101014A010001014B0101014C000101014D010101004E0101014F010100015001010151010001015201010153000101
015401010100550101015601010001570101015801000101590101445F0043757272656E74005363656E650000000000000000000000005B270000610E200000
00000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000001010101010001000000000000000000
00000000020002020202020000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000101000101
01010101010001010101010101000101010101010100010101010101010067676767676767006767676767676700676767676767670067676700000000000000
00000000000000000000000000000000000000000000000000000001010001016767676700000000003030303100303030313030300031303030313030003031
30303031300031204261736963000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000
00000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000
00000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000
00000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000
00000000000000000000000000000000000000000000000000000000000000000000000000000000003031204200617369630000000000000000000000000000
00000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000
00000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000
00000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000
00000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000
00000000000000000000000000003031204261736900630000000000000000000000000000000000000000000000000000000000000000000000000000000000
00000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000
00000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000
00000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000
00000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000003031200042617369630000000000
00000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000
00000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000
00000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000
00000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000
00000000000000000000000000000000000000000000003031204261730069630000000000000000000000000000000000000000000000000000000000000000
00000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000
00000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000
00000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000
00000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000003031002042
61736963000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000
00000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000
00000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000
00000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000
0000000000000000000000000000000000000000000000000000000000000000380025001315003500570048002A390007005F003851002500130035002A5700
480039000755005F00380025000A130035005700485500390007005F00283800250013003555005700480039002A07005F0038002545001300350057002A4800
390007005F54003800250013002A35005700480039550007005F001F00222A00350007005A540053004C007600007E001F002A0035150007005A005300204C00
76007E001F01002A00350007002A5A0053004C007600007E001F002A000A350007005A005350004C0076007E00001F002A0035000755005A0053004C00007600
7E001F002A0500350007005A002853004C0076007E00001E2D3C495649003C58601E2D3C490056493C58601E2D003C4956493C5860001E2D3C4956493C005860
1E2D3C495600493C58601E2D3C004956493C58600100010101010000010002010101010100000001020101010100010000010201010001010100000102000101
01010100000001020101010101000000010264646400645A6464646464006464645A6464640064646464645A640064646464646464005A646464646464006464
5A6464646400646464645A646400646446465E4038004050464046465E004038405046404600465E4038405046004046465E4038400050464046465E40003840
5046404646005E403840504640001E324745443220004B771E324745440032204B771E324700454432204B771E003247454432204B00771E324745443200204B
771E324745004432204B770500024D00040107002B44000A006A007E002A120105004D0004140107002B000A00226A007E0012010551004D0004010700222B00
0A006A007E1500120105004D000A040107002B000A11006A007E0012012805004D0004010751002B000A006A000A7E00120105004D4500040107002B00080A00
6A007E001254010C0C0C0C0C0C000C0C0C0C0C0C0C000C0C0C0C0C0C0C000C0C0C0C0C0C0C000C0C0C0C0C0C0C000C0C0C0C0C0C0C000C0C0C0C0C0C0C000C0C
0C0C0C0C700074717670717374007670747176707100737476707471760070717374767074007176707173747600707471767071730074767074717670007173
7476340017050064002E000401086A00340066001D5401340017006400282E0004016A0034450066001D01340022170064002E000444016A00340066002A1D01
340017006414002E0004016A0022340066001D01345100170064002E002204016A0034006615001D01340017000A64002E0004016A1100340066001D01284835
4743445060006B6F48354743440050606B6F48354700434450606B6F48003547434450606B006F48354743445000606B6F48354743004450606B6F3400025200
0D013B006944001E0020003F002A5200340052000D54013B0069001E002220003F00520034550052000D013B002269001E0020003F15005200340052002A0D01
3B0069001E110020003F0052002A340052000D013B510069001E0020000A3F00520034005255000D013B006900081E0020003F005255000C0E10101310001010
100C0E10100013101010100C0E0010101310101010000C0E10101310100010100C0E10101300101010100C0E100010131010101020001E1C1E1F20241E000B20
1E1C1E1F2000241E0B201E1C1E001F20241E0B201E001C1E1F20241E0B00201E1C1E1F2024001E0B201E1C1E1F0020241E0B34001805005900230075000A7A00
7C00500010550034001800590028230075007A007C55005000100034002A1800590023007545007A007C0050002A100034001800595400230075007A002A7C00
500010003455001800590023002275007A007C005055001000340018002A5900230075007A15007C00500010002A3400340034003455003400340034002A3400
340034003455003400340034002A3400340034003455003400340034002A3400340034003455003400340034002A3400340034003455003400340034002A3400
340034003455003400340034002A3400340034003455003400340034002A34003400340034550034000000000020000000000000000000000000000000006464
646464643801003800380038002A380038001F001F55001F001F001F002A1F001E1E1E1E1E401E01010101010100646464646464460046464646460101000101
01011E1E1E001E1E1E050005000A0500050005000555000C0C0C0C0C0C00000000000000010001010101017070007070707034003405003400340034002A3400
0101010101400148484848484800340034003400345500340034000C0C280C0C0C0C0101010001010120202020002020340034003415003400340034002A3400
3400340034550034003400000028170A0204321D08000C1B7F2001010100016767676700600009084F00000000003232131300003D003D323228281E1E000000
404000000800080202000001010032323232404040004001012E2E0000002F2F464635351C001C00002F2F000000040402020000000000000000004040004040
00006464000000424250501E1E001D1D31312A2A00000001010202000000000000000000400040404003034B4B000000282832325000505A5A28282B2B000000
060602020000000000000000000040404040000014001400000F000F000A7676660066000014000101010167670067670000000000007F7F7F7F7F7F7F7F7F7F
7F7F7F7F7F7F7F7F7F7F7F7F7F7F7F7F7F7F7F7F7F7F7F7F7F7F7F7F7F7F7F7F7F7F7F7F7F7F7F7F7F7F7F7F017E010101010101010067676767676767006700
0000000000000000000000000000000000000000000000000000000000000000000000000000000000000100000040000040037E000000007F00070101000101
010101010100010101010000000000010117171111006D006D0065653C51003C0000000000200101373728287F01007F00520052002A01011414000001000101
010101000000212131316D006D05003A3A6300630000010000116B02270000136B02270009006B022700245D070044000000000000000DF7
"""